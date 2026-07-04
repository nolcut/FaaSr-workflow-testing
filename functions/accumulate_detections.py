import json
import os
import tempfile


def accumulate_detections(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Accumulate all detections from parallel detect functions into a final consolidated payload.
    Reads detection results from multiple parallel detect function outputs (N=2 batches),
    merges all detections into a single list, and outputs the final consolidated list
    containing all {label, class, score} entries where score > 0.5.
    """
    faasr_log("accumulate_detections starting")

    with tempfile.TemporaryDirectory() as tmpdir:
        all_detections = []

        # Process each input detection file
        input_files = [input1, input2]

        for detection_file in input_files:
            local_file = os.path.join(tmpdir, detection_file)

            # Download the detection file
            faasr_get_file(
                local_file=local_file,
                remote_folder=folder,
                remote_file=detection_file
            )

            if not os.path.exists(local_file) or os.path.getsize(local_file) == 0:
                error_msg = f"Failed to download detection file '{detection_file}' from folder '{folder}'"
                faasr_log(error_msg)
                raise RuntimeError(error_msg)

            faasr_log(f"Downloaded detection file: {detection_file}")

            # Load the detections
            with open(local_file, "r") as f:
                detections = json.load(f)

            # Filter detections with score > 0.5 and add to consolidated list
            for detection in detections:
                if detection.get("score", 0) > 0.5:
                    all_detections.append({
                        "label": detection["label"],
                        "class": detection["class"],
                        "score": detection["score"]
                    })

            faasr_log(f"Loaded {len(detections)} detections from {detection_file}")

        faasr_log(f"Total consolidated detections with score > 0.5: {len(all_detections)}")

        # Write the final consolidated output
        local_output = os.path.join(tmpdir, "final_detections.json")
        with open(local_output, "w") as f:
            json.dump(all_detections, f, indent=2)

        # Upload to S3
        faasr_put_file(
            local_file=local_output,
            remote_folder=folder,
            remote_file=output1
        )
        faasr_log(f"Uploaded consolidated detections: {output1}")

        faasr_log("accumulate_detections completed")
