import json
import os
import pickle
import tempfile

import cv2
import numpy as np


# COCO 80 class labels (0-indexed for the model)
COCO_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush"
]


def detect(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """
    Loads Faster R-CNN ResNet-50 COCO model and runs detection on a batch of frames.
    Filters detections with confidence > 0.5 and outputs results as JSON.
    """
    # Get rank for parallel execution
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"detect function starting with rank {rank} of {r['max_rank']}")

    # Substitute rank into filenames
    batch_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download the batch of frames
        batch_path = os.path.join(tmpdir, batch_file)
        faasr_get_file(local_file=batch_path, remote_folder=folder, remote_file=batch_file)

        if not os.path.exists(batch_path) or os.path.getsize(batch_path) == 0:
            faasr_log(f"ERROR: Failed to download batch file {batch_file} or file is empty")
            raise RuntimeError(f"Failed to download batch file {batch_file}")

        # Load the batch of frames
        with open(batch_path, "rb") as f:
            frames = pickle.load(f)

        faasr_log(f"Loaded {len(frames)} frames from batch {rank}")

        # Download the model weights (pb file)
        weights_path = os.path.join(tmpdir, input2)
        faasr_get_file(local_file=weights_path, remote_folder=folder, remote_file=input2)

        if not os.path.exists(weights_path) or os.path.getsize(weights_path) == 0:
            faasr_log(f"ERROR: Failed to download model weights {input2} or file is empty")
            raise RuntimeError(f"Failed to download model weights {input2}")

        # Download the model config (pbtxt file)
        config_path = os.path.join(tmpdir, input3)
        faasr_get_file(local_file=config_path, remote_folder=folder, remote_file=input3)

        if not os.path.exists(config_path) or os.path.getsize(config_path) == 0:
            faasr_log(f"ERROR: Failed to download model config {input3} or file is empty")
            raise RuntimeError(f"Failed to download model config {input3}")

        faasr_log(f"Model files downloaded: {input2}, {input3}")

        # Load the Faster R-CNN model using OpenCV
        net = cv2.dnn.readNetFromTensorflow(weights_path, config_path)
        faasr_log("Faster R-CNN model loaded successfully")

        # Run detection on each frame
        all_detections = []
        confidence_threshold = 0.5

        for frame_idx, frame in enumerate(frames):
            # Prepare the frame for the network
            # Faster R-CNN expects BGR input, which OpenCV already provides
            height, width = frame.shape[:2]

            # Create blob from image
            # For Faster R-CNN, we typically don't resize but pass the original size
            blob = cv2.dnn.blobFromImage(
                frame,
                swapRB=True,  # Convert BGR to RGB
                crop=False
            )

            net.setInput(blob)

            # Run inference
            detections = net.forward()

            # Parse detections
            # Faster R-CNN detection output format: [batch_id, class_id, confidence, x1, y1, x2, y2]
            frame_detections = []

            for detection in detections[0, 0]:
                confidence = float(detection[2])

                if confidence > confidence_threshold:
                    # The model returns class_id as 1-indexed in COCO (background=0)
                    # We need to map to 0-indexed COCO 80 labels
                    class_id = int(detection[1])

                    # Map to 0-indexed for COCO labels (class_id 1 = person = index 0)
                    coco_index = class_id - 1

                    if 0 <= coco_index < len(COCO_LABELS):
                        label = COCO_LABELS[coco_index]
                    else:
                        label = f"class_{class_id}"

                    frame_detections.append({
                        "label": label,
                        "class": class_id,
                        "score": round(confidence, 4)
                    })

            all_detections.append({
                "frame_index": frame_idx,
                "detections": frame_detections
            })

            faasr_log(f"Frame {frame_idx}: found {len(frame_detections)} detections with score > {confidence_threshold}")

        # Prepare output
        output_data = {
            "rank": rank,
            "num_frames": len(frames),
            "frames": all_detections
        }

        # Write output JSON
        output_path = os.path.join(tmpdir, output_file)
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        # Upload results
        faasr_put_file(local_file=output_path, remote_folder=folder, remote_file=output_file)

        total_detections = sum(len(fd["detections"]) for fd in all_detections)
        faasr_log(f"detect complete for rank {rank}: {total_detections} total detections across {len(frames)} frames")
