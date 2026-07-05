"""
accumulate_detections: Accumulates detections from all parallel detect functions
into the final payload. Reads detection results from each of the N=2 parallel
detect workers (batch_detections_1.json and batch_detections_2.json), merges all
detections from all batches into a single combined result, keeping only detections
with score > 0.5. Outputs the final accumulated detections as final_detections.json.
"""

import json
import os
import tempfile


def accumulate_detections(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Accumulates detections from all parallel detect workers into final payload.

    Args:
        folder: S3 folder name
        input1: First batch detections file (batch_detections_1.json)
        input2: Second batch detections file (batch_detections_2.json)
        output1: Output file for combined detections (final_detections.json)
    """
    faasr_log("Starting accumulation of detections from parallel workers")

    # List of input detection files
    input_files = [input1, input2]

    with tempfile.TemporaryDirectory() as tmpdir:
        all_detections = []

        # Download and process each batch detection file
        for batch_file in input_files:
            local_file = os.path.join(tmpdir, batch_file)
            faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=batch_file)

            # Verify file was downloaded
            if not os.path.exists(local_file) or os.path.getsize(local_file) == 0:
                faasr_log(f"ERROR: Failed to download or empty file {batch_file}")
                raise RuntimeError(f"Failed to download batch detections file {batch_file}")

            # Load detections from batch
            with open(local_file, 'r') as f:
                batch_detections = json.load(f)

            faasr_log(f"Loaded {len(batch_detections)} detections from {batch_file}")

            # Filter to keep only detections with score > 0.5
            # (should already be filtered by detect functions, but verify)
            filtered_detections = [d for d in batch_detections if d.get('score', 0) > 0.5]

            if len(filtered_detections) < len(batch_detections):
                faasr_log(f"Filtered out {len(batch_detections) - len(filtered_detections)} detections with score <= 0.5")

            all_detections.extend(filtered_detections)

        faasr_log(f"Total accumulated detections: {len(all_detections)}")

        # Write final accumulated detections
        local_output = os.path.join(tmpdir, output1)
        with open(local_output, 'w') as f:
            json.dump(all_detections, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)

        faasr_log(f"Uploaded final detections to {output1}")
        faasr_log("Accumulation complete")
