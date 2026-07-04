import json
import os
import tempfile


def accumulate_detections(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Accumulate all detections from the parallel detect functions (N=2 batch detection outputs)
    and return the final payload Y.

    Reads detection results from each parallel detect function (batch 0 and batch 1),
    which are JSON files containing detection arrays with label, class, and score fields.
    Combines all detections from both batches into a single unified result.
    """
    faasr_log("Starting accumulate_detections")

    # Use faasr_get_folder_list to discover all detection files from the ranked predecessor
    # The folder prefix helps filter to detection files
    all_files = faasr_get_folder_list(prefix=folder)
    faasr_log(f"Found files in folder: {all_files}")

    # Collect all detections from input files
    all_detections = []

    # Process input1 (detections from batch 0)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp1:
        local_file1 = tmp1.name

    try:
        faasr_get_file(local_file=local_file1, remote_folder=folder, remote_file=input1)
        with open(local_file1, 'r') as f:
            detections1 = json.load(f)
        faasr_log(f"Loaded {len(detections1)} detections from {input1}")
        all_detections.extend(detections1)
    except Exception as e:
        faasr_log(f"Error reading {input1}: {e}")
        raise
    finally:
        if os.path.exists(local_file1):
            os.remove(local_file1)

    # Process input2 (detections from batch 1)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp2:
        local_file2 = tmp2.name

    try:
        faasr_get_file(local_file=local_file2, remote_folder=folder, remote_file=input2)
        with open(local_file2, 'r') as f:
            detections2 = json.load(f)
        faasr_log(f"Loaded {len(detections2)} detections from {input2}")
        all_detections.extend(detections2)
    except Exception as e:
        faasr_log(f"Error reading {input2}: {e}")
        raise
    finally:
        if os.path.exists(local_file2):
            os.remove(local_file2)

    faasr_log(f"Total accumulated detections: {len(all_detections)}")

    # Write the combined results to output file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_out:
        local_output = tmp_out.name

    try:
        with open(local_output, 'w') as f:
            json.dump(all_detections, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded final detections to {output1}")
    finally:
        if os.path.exists(local_output):
            os.remove(local_output)

    faasr_log("accumulate_detections complete")
