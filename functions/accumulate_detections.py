import json
import tempfile
import os


def accumulate_detections(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Accumulates all detections from N=2 parallel detect_objects workers.

    Reads detection result files from each parallel worker (batch 1 and batch 2),
    merges all detections into a single consolidated list, and writes the final
    accumulated detections as a JSON file.
    """
    faasr_log("Starting accumulate_detections")

    all_detections = []
    input_files = [input1, input2]

    for input_file in input_files:
        # Download detection file from S3
        local_file = os.path.join(tempfile.gettempdir(), input_file)
        faasr_log(f"Downloading {input_file}")
        faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=input_file)

        # Read and parse JSON
        with open(local_file, 'r') as f:
            data = json.load(f)

        batch_id = data.get("batch_id", "unknown")
        rank = data.get("rank", "unknown")
        detections = data.get("detections", [])

        faasr_log(f"Batch {batch_id} (rank {rank}): found {len(detections)} detections")

        # Add all detections to accumulated list
        all_detections.extend(detections)

        # Clean up local file
        os.remove(local_file)

    faasr_log(f"Total accumulated detections: {len(all_detections)}")

    # Build final output structure
    final_output = {
        "total_detections": len(all_detections),
        "detections": all_detections
    }

    # Write final detections to local file
    local_output = os.path.join(tempfile.gettempdir(), output1)
    with open(local_output, 'w') as f:
        json.dump(final_output, f, indent=2)

    # Upload to S3
    faasr_log(f"Uploading final detections to {output1}")
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)

    # Clean up
    os.remove(local_output)

    faasr_log("accumulate_detections complete")
