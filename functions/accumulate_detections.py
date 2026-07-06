import json
import os
import tempfile


def accumulate_detections(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Accumulate all detections from the parallel detect functions into final payload Y.

    Reads detection result files from N=2 parallel detect functions, combines all
    detections from all batches into a single unified result.

    Args:
        folder: Remote folder name
        input1: First detection file (detections_1.json)
        input2: Second detection file (detections_2.json)
        output1: Output file for accumulated detections (final_detections.json)
    """
    faasr_log("Starting accumulate_detections")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download detection files from both ranked detect functions
        local_file1 = os.path.join(tmpdir, "detections_1.json")
        local_file2 = os.path.join(tmpdir, "detections_2.json")

        faasr_get_file(local_file=local_file1, remote_folder=folder, remote_file=input1)
        faasr_get_file(local_file=local_file2, remote_folder=folder, remote_file=input2)

        # Validate files were downloaded
        if not os.path.exists(local_file1) or os.path.getsize(local_file1) == 0:
            faasr_log(f"ERROR: Failed to download {input1} or file is empty")
            raise RuntimeError(f"Failed to download {input1} or file is empty")

        if not os.path.exists(local_file2) or os.path.getsize(local_file2) == 0:
            faasr_log(f"ERROR: Failed to download {input2} or file is empty")
            raise RuntimeError(f"Failed to download {input2} or file is empty")

        faasr_log(f"Downloaded detection files: {input1}, {input2}")

        # Load detection data from both files
        with open(local_file1, "r") as f:
            data1 = json.load(f)
        with open(local_file2, "r") as f:
            data2 = json.load(f)

        faasr_log(f"Loaded detections from batch {data1.get('batch_num', 'unknown')} "
                  f"and batch {data2.get('batch_num', 'unknown')}")

        # Combine all frame detections from both batches
        # Each file has structure:
        # {
        #   "rank": int,
        #   "batch_num": int,
        #   "total_frames": int,
        #   "frame_detections": [
        #     {"frame_idx": int, "detections": [{"label": str, "class": int, "score": float}]}
        #   ]
        # }

        all_frame_detections = []

        # Add frame detections from first batch
        for frame_data in data1.get("frame_detections", []):
            all_frame_detections.append(frame_data)

        # Add frame detections from second batch
        for frame_data in data2.get("frame_detections", []):
            all_frame_detections.append(frame_data)

        # Sort by frame index to maintain temporal order
        all_frame_detections.sort(key=lambda x: x.get("frame_idx", 0))

        # Also create a flat list of all detections with frame context
        all_detections_flat = []
        for frame_data in all_frame_detections:
            frame_idx = frame_data.get("frame_idx", 0)
            for detection in frame_data.get("detections", []):
                all_detections_flat.append({
                    "frame_idx": frame_idx,
                    "label": detection["label"],
                    "class": detection["class"],
                    "score": detection["score"]
                })

        # Count total detections
        total_detections = len(all_detections_flat)
        total_frames = len(all_frame_detections)

        faasr_log(f"Accumulated {total_detections} detections from {total_frames} frames")

        # Prepare final output
        output_data = {
            "total_frames": total_frames,
            "total_detections": total_detections,
            "frame_detections": all_frame_detections,
            "all_detections": all_detections_flat
        }

        # Write output
        local_output_file = os.path.join(tmpdir, "final_detections.json")
        with open(local_output_file, "w") as f:
            json.dump(output_data, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output_file, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded final accumulated detections to {output1}")

    faasr_log("accumulate_detections completed")
