import json
import os


def accumulate(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Collects all detection results from parallel detect functions.

    Downloads detection JSON files from each of the 2 parallel detect invocations
    (detections_batch_1.json and detections_batch_2.json). Each input file contains
    a list of detections with {class, score} where score > 0.5. Accumulates all
    detections into a single combined list and writes to final_detections.json.
    """
    faasr_log("Starting accumulate: collecting detection results from parallel detect functions")

    # List of input files to accumulate
    input_files = [input1, input2]

    # Accumulated detections from all batches
    all_detections = []

    for remote_file in input_files:
        local_file = os.path.join("/tmp", remote_file)

        faasr_log(f"Downloading {remote_file} from folder {folder}")
        faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=remote_file)

        # Read and parse the detection JSON
        with open(local_file, "r") as f:
            detections = json.load(f)

        if not isinstance(detections, list):
            faasr_log(f"ERROR: Expected list of detections in {remote_file}, got {type(detections)}")
            raise ValueError(f"Invalid format in {remote_file}: expected list of detections")

        faasr_log(f"Read {len(detections)} detections from {remote_file}")
        all_detections.extend(detections)

        # Clean up local file
        os.remove(local_file)

    faasr_log(f"Total accumulated detections: {len(all_detections)}")

    # Write combined detections to output file
    output_local = os.path.join("/tmp", output1)
    with open(output_local, "w") as f:
        json.dump(all_detections, f, indent=2)

    faasr_log(f"Uploading final detections to {folder}/{output1}")
    faasr_put_file(local_file=output_local, remote_folder=folder, remote_file=output1)

    # Clean up
    os.remove(output_local)

    faasr_log(f"Accumulate complete: {len(all_detections)} total detections written to {output1}")
