import json
import os
import tempfile


def accumulate(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Collects detection results from parallel detect functions (N=2 batches from F=10 frames
    with batch size B=5). Reads detection JSON files from each parallel detect worker,
    accumulates all detections into a single final payload Y.
    """
    faasr_log("accumulate function starting")

    # Use faasr_get_folder_list to discover detection files from ranked predecessor
    # The function receives input1 and input2 as specific filenames, but we follow
    # the fan-in pattern: discover files with faasr_get_folder_list and read each one
    all_files = faasr_get_folder_list(prefix=folder)
    faasr_log(f"Found {len(all_files)} files in folder with prefix '{folder}'")

    # Filter for detection files (detections_*.json pattern)
    detection_files = []
    for full_key in all_files:
        basename = full_key.rsplit("/", 1)[-1]
        if basename.startswith("detections_") and basename.endswith(".json"):
            detection_files.append(basename)

    faasr_log(f"Found {len(detection_files)} detection files: {detection_files}")

    if not detection_files:
        # Fall back to using the provided input parameters
        detection_files = [input1, input2]
        faasr_log(f"No detection files found via folder list, using provided inputs: {detection_files}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Accumulate all frames from all batches
        all_frames = []
        total_detections = 0

        for detection_file in sorted(detection_files):
            local_path = os.path.join(tmpdir, detection_file)
            faasr_get_file(local_file=local_path, remote_folder=folder, remote_file=detection_file)

            if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
                faasr_log(f"ERROR: Failed to download detection file {detection_file} or file is empty")
                raise RuntimeError(f"Failed to download detection file {detection_file}")

            with open(local_path, "r") as f:
                batch_data = json.load(f)

            rank = batch_data.get("rank", "unknown")
            num_frames = batch_data.get("num_frames", 0)
            frames = batch_data.get("frames", [])

            faasr_log(f"Processing batch from rank {rank}: {num_frames} frames")

            # Add batch info to each frame for traceability
            for frame in frames:
                frame_detections = frame.get("detections", [])
                total_detections += len(frame_detections)
                # Store with batch rank info
                all_frames.append({
                    "batch_rank": rank,
                    "frame_index": frame.get("frame_index"),
                    "detections": frame_detections
                })

        # Build final accumulated output
        output_data = {
            "total_batches": len(detection_files),
            "total_frames": len(all_frames),
            "total_detections": total_detections,
            "frames": all_frames
        }

        # Write output JSON
        output_path = os.path.join(tmpdir, output1)
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        # Upload results
        faasr_put_file(local_file=output_path, remote_folder=folder, remote_file=output1)

        faasr_log(f"accumulate complete: {total_detections} total detections from {len(all_frames)} frames across {len(detection_files)} batches")
