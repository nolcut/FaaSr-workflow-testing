import json
import os
import pickle
import tempfile

import cv2
import numpy as np

# COCO 90-category ID to name mapping (TensorFlow Object Detection API format)
# The model returns 1-indexed category IDs; after subtracting 1, we get 0-89 indices
# Some IDs are unused in COCO (gaps), but the model may still output them
COCO_ID_TO_NAME = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
    10: "fire hydrant", 12: "stop sign", 13: "parking meter", 14: "bench",
    15: "bird", 16: "cat", 17: "dog", 18: "horse", 19: "sheep",
    20: "cow", 21: "elephant", 22: "bear", 23: "zebra", 24: "giraffe",
    26: "backpack", 27: "umbrella", 30: "handbag", 31: "tie", 32: "suitcase",
    33: "frisbee", 34: "skis", 35: "snowboard", 36: "sports ball", 37: "kite",
    38: "baseball bat", 39: "baseball glove", 40: "skateboard", 41: "surfboard",
    42: "tennis racket", 43: "bottle", 45: "wine glass", 46: "cup",
    47: "fork", 48: "knife", 49: "spoon", 50: "bowl", 51: "banana",
    52: "apple", 53: "sandwich", 54: "orange", 55: "broccoli", 56: "carrot",
    57: "hot dog", 58: "pizza", 59: "donut", 60: "cake", 61: "chair",
    62: "couch", 63: "potted plant", 64: "bed", 66: "dining table",
    69: "toilet", 70: "tv", 71: "laptop", 72: "mouse", 73: "remote",
    74: "keyboard", 75: "cell phone", 76: "microwave", 77: "oven",
    78: "toaster", 79: "sink", 80: "refrigerator", 81: "book", 82: "clock",
    83: "vase", 84: "scissors", 85: "teddy bear", 86: "hair drier", 87: "toothbrush"
}


def detect_objects(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """
    Load Faster R-CNN ResNet-50 COCO model and run object detection on a batch of frames.
    Filter detections keeping only those with confidence score > 0.5.
    Output detection results as JSON.
    """
    # Get rank for this parallel instance
    r = faasr_rank()
    rank = r["rank"]

    faasr_log(f"detect_objects starting for rank {rank} of {r['max_rank']}")

    # Format filenames with rank
    batch_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download the batch pickle file
        local_batch = os.path.join(tmpdir, "batch.pkl")
        faasr_get_file(local_file=local_batch, remote_folder=folder, remote_file=batch_file)

        if not os.path.exists(local_batch) or os.path.getsize(local_batch) == 0:
            error_msg = f"Failed to download batch file '{batch_file}' from folder '{folder}'"
            faasr_log(error_msg)
            raise RuntimeError(error_msg)

        faasr_log(f"Downloaded batch file: {batch_file}")

        # Load the batch data
        with open(local_batch, "rb") as f:
            batch_data = pickle.load(f)

        frames = batch_data["frames"]
        faasr_log(f"Loaded {len(frames)} frames from batch")

        # Download model weights file
        local_weights = os.path.join(tmpdir, "frozen_inference_graph.pb")
        faasr_get_file(local_file=local_weights, remote_folder=folder, remote_file=input2)

        if not os.path.exists(local_weights) or os.path.getsize(local_weights) == 0:
            error_msg = f"Failed to download model weights '{input2}' from folder '{folder}'"
            faasr_log(error_msg)
            raise RuntimeError(error_msg)

        # Download model config file
        local_config = os.path.join(tmpdir, "config.pbtxt")
        faasr_get_file(local_file=local_config, remote_folder=folder, remote_file=input3)

        if not os.path.exists(local_config) or os.path.getsize(local_config) == 0:
            error_msg = f"Failed to download model config '{input3}' from folder '{folder}'"
            faasr_log(error_msg)
            raise RuntimeError(error_msg)

        faasr_log("Downloaded model files")

        # Load the Faster R-CNN model using OpenCV DNN
        net = cv2.dnn.readNetFromTensorflow(local_weights, local_config)
        faasr_log("Loaded Faster R-CNN model")

        # Process each frame and collect detections
        all_detections = []

        for frame_idx, frame in enumerate(frames):
            # Get frame dimensions
            h, w = frame.shape[:2]

            # Preprocess the frame using cv2.dnn.blobFromImage
            # Faster R-CNN typically expects 300x300 or 600x600 input
            blob = cv2.dnn.blobFromImage(
                frame,
                swapRB=True,
                crop=False
            )

            # Set the input and run forward pass
            net.setInput(blob)
            detections = net.forward()

            # Parse detections
            # Output shape is [1, 1, num_detections, 7]
            # Each detection: [batch_id, class_id, confidence, x1, y1, x2, y2]
            for i in range(detections.shape[2]):
                confidence = float(detections[0, 0, i, 2])

                # Filter by confidence threshold > 0.5
                if confidence > 0.5:
                    # Class ID from detection (1-indexed from TensorFlow model, convert to 0-indexed)
                    class_id_raw = int(detections[0, 0, i, 1])
                    # TensorFlow models use 1-indexed classes, convert to 0-indexed
                    class_id = class_id_raw - 1

                    # Map to COCO label name using the ID mapping
                    label = COCO_ID_TO_NAME.get(class_id, f"unknown_{class_id}")

                    detection_obj = {
                        "label": label,
                        "class": class_id,
                        "score": round(confidence, 4)
                    }
                    all_detections.append(detection_obj)

            faasr_log(f"Processed frame {frame_idx + 1}/{len(frames)}")

        faasr_log(f"Total detections with score > 0.5: {len(all_detections)}")

        # Write output JSON
        local_output = os.path.join(tmpdir, "detections.json")
        with open(local_output, "w") as f:
            json.dump(all_detections, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Uploaded detection results: {output_file}")

        faasr_log(f"detect_objects completed for rank {rank}")
