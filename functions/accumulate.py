import json
import os
import re


def accumulate(folder: str, input1: str, output1: str) -> None:
    """
    Collects detection results from all parallel detect functions and merges them
    into a single accumulated result containing all detections across all video frames.
    """
    faasr_log("Starting accumulate function")

    # Discover all files in the folder using faasr_get_folder_list
    all_files = faasr_get_folder_list(prefix=folder)
    faasr_log(f"Found {len(all_files)} files in folder: {all_files}")

    # Filter for detection files (detections_*.json pattern)
    # Extract pattern from input1 template (e.g., "detections_{rank}.json")
    pattern_base = input1.replace("{rank}", r"(\d+)")
    detection_files = []
    for full_key in all_files:
        basename = full_key.rsplit("/", 1)[-1]
        if re.match(pattern_base, basename):
            detection_files.append(basename)

    faasr_log(f"Found {len(detection_files)} detection files: {detection_files}")

    if len(detection_files) == 0:
        faasr_log("ERROR: No detection files found")
        raise RuntimeError("No detection files found to accumulate")

    # Accumulate all detections from all files
    all_detections = []

    for detection_file in sorted(detection_files):
        local_file = f"temp_{detection_file}"
        faasr_log(f"Downloading {detection_file}")
        faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=detection_file)

        try:
            with open(local_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    faasr_log(f"WARNING: {detection_file} is empty")
                    detections = []
                else:
                    detections = json.loads(content)

            if not isinstance(detections, list):
                faasr_log(f"ERROR: {detection_file} does not contain a list")
                raise RuntimeError(f"Invalid format in {detection_file}: expected list")

            faasr_log(f"Loaded {len(detections)} detections from {detection_file}")
            all_detections.extend(detections)
        finally:
            # Clean up temp file
            if os.path.exists(local_file):
                os.remove(local_file)

    faasr_log(f"Total accumulated detections: {len(all_detections)}")

    # Write the merged results to local file
    local_output = "all_detections_local.json"
    with open(local_output, 'w') as f:
        json.dump(all_detections, f, indent=2)

    # Upload to S3
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded merged detections to {output1}")

    # Clean up
    if os.path.exists(local_output):
        os.remove(local_output)

    faasr_log("Accumulate function completed successfully")
