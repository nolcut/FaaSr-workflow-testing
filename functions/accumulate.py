import json
import os
import tempfile


def accumulate(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Accumulates all detections from the parallel detect functions into the final payload Y.
    Reads detection results from each parallel detect worker (N=2 batch detection outputs from
    the map phase). Combines all detections into a single unified result containing all objects
    detected across all video frames with confidence score > 0.5. Each detection includes the
    label (from COCO 80 dataset, zero-indexed), class_id, and confidence score.
    """
    faasr_log("Starting accumulate function")

    # Discover all detection files from the folder
    # faasr_get_folder_list returns FULL object keys including the folder prefix
    all_files = faasr_get_folder_list(prefix=folder)
    faasr_log(f"Found files in folder: {all_files}")

    # Filter for detection files (detections_*.json pattern)
    detection_files = []
    for full_path in all_files:
        # Extract basename from full path
        basename = full_path.rsplit("/", 1)[-1]
        if basename.startswith("detections_") and basename.endswith(".json"):
            detection_files.append(basename)

    faasr_log(f"Found {len(detection_files)} detection files: {detection_files}")

    if not detection_files:
        faasr_log("ERROR: No detection files found")
        raise RuntimeError("No detection files found in folder")

    # Collect all frame detections from all detection files
    all_frame_detections = []
    total_batches_processed = 0

    for det_file in sorted(detection_files):
        faasr_log(f"Processing detection file: {det_file}")

        # Download the detection file
        local_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=det_file)

        # Verify file exists and has content
        if not os.path.exists(local_file) or os.path.getsize(local_file) == 0:
            faasr_log(f"ERROR: Failed to download detection file {det_file} or file is empty")
            os.unlink(local_file)
            raise RuntimeError(f"Failed to download detection file {det_file}")

        # Load the detection data
        with open(local_file, 'r') as f:
            detection_data = json.load(f)
        os.unlink(local_file)

        # Extract frame detections from this batch
        frame_detections = detection_data.get('frame_detections', [])
        batch_id = detection_data.get('batch_id', 'unknown')
        rank = detection_data.get('rank', 'unknown')

        faasr_log(f"Batch {batch_id} (rank {rank}): {len(frame_detections)} frames")

        all_frame_detections.extend(frame_detections)
        total_batches_processed += 1

    # Sort frame detections by frame_index to ensure correct ordering
    all_frame_detections.sort(key=lambda x: x.get('frame_index', 0))

    # Calculate total detection count
    total_detections = sum(len(fd.get('detections', [])) for fd in all_frame_detections)
    total_frames = len(all_frame_detections)

    faasr_log(f"Combined {total_frames} frames with {total_detections} total detections")

    # Build the final output payload Y
    final_output = {
        "total_frames": total_frames,
        "total_batches": total_batches_processed,
        "total_detections": total_detections,
        "frame_detections": all_frame_detections
    }

    # Write to local file and upload
    local_output = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w').name
    with open(local_output, 'w') as f:
        json.dump(final_output, f, indent=2)

    faasr_log(f"Uploading final detection results: {output1}")
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    os.unlink(local_output)

    faasr_log(f"Accumulate complete: {total_frames} frames, {total_detections} detections from {total_batches_processed} batches")
