import json
import tempfile
import os


def accumulate_detections(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Collects detection results from all parallel detect functions and merges them
    into a single accumulated result containing all detections across all frames.

    Each parallel detect function outputs a JSON file containing detections for its
    batch of frames. This accumulator reads all detection result files and merges
    them into a single output file with frame information preserved.
    """
    faasr_log("accumulate_detections: Starting accumulation of detection results")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Discover all detection files from the ranked predecessor using folder listing
        # faasr_get_folder_list returns FULL object keys including the folder prefix
        all_keys = faasr_get_folder_list(prefix=folder)

        # Filter to find detection files (detections_*.json)
        detection_keys = [
            key for key in all_keys
            if key.rsplit("/", 1)[-1].startswith("detections_")
            and key.endswith(".json")
        ]

        faasr_log(f"Found {len(detection_keys)} detection files to accumulate")

        if len(detection_keys) == 0:
            faasr_log("ERROR: No detection files found in folder")
            raise RuntimeError("No detection files found to accumulate")

        # Collect all frame detections from all workers
        all_frame_detections = []
        total_detections = 0

        for key in detection_keys:
            # Extract just the basename for faasr_get_file
            filename = key.rsplit("/", 1)[-1]
            local_file = os.path.join(tmpdir, filename)

            faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=filename)

            if not os.path.exists(local_file) or os.path.getsize(local_file) == 0:
                faasr_log(f"ERROR: Failed to download detection file {filename}")
                raise RuntimeError(f"Failed to download detection file {filename}")

            with open(local_file, 'r') as f:
                detection_data = json.load(f)

            batch_id = detection_data.get("batch_id", "unknown")
            rank = detection_data.get("rank", "unknown")
            num_frames = detection_data.get("num_frames", 0)
            frame_detections = detection_data.get("frame_detections", [])

            faasr_log(f"Processing batch {batch_id} (rank {rank}): {num_frames} frames")

            # Add all frame detections to accumulated list
            for frame_data in frame_detections:
                frame_index = frame_data.get("frame_index")
                detections = frame_data.get("detections", [])

                all_frame_detections.append({
                    "frame_index": frame_index,
                    "batch_id": batch_id,
                    "detections": detections
                })

                total_detections += len(detections)

        # Sort by frame_index to maintain temporal order
        all_frame_detections.sort(key=lambda x: x.get("frame_index", 0))

        # Build the accumulated output
        accumulated_output = {
            "total_frames": len(all_frame_detections),
            "total_detections": total_detections,
            "frame_detections": all_frame_detections
        }

        faasr_log(f"Accumulated {total_detections} detections across {len(all_frame_detections)} frames")

        # Write accumulated output to local file
        local_output = os.path.join(tmpdir, "accumulated_detections.json")
        with open(local_output, 'w') as f:
            json.dump(accumulated_output, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded accumulated detections to {output1}")

    faasr_log("accumulate_detections: Completed successfully")
