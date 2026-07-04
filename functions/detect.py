"""
Detect function for video analysis workflow.

Loads Faster R-CNN ResNet-50 COCO model, processes a batch of base64-encoded frames,
runs object detection on each frame, and outputs detections with confidence > 0.5.
"""

import base64
import json
import os
import tempfile

import cv2
import numpy as np


# COCO class labels (1-indexed in COCO, so class_id 1 -> labels[0])
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
    Detect objects in video frames using Faster R-CNN ResNet-50 COCO model.

    Args:
        folder: S3 folder name
        input1: Input batch filename template with {rank} placeholder (batch_{rank}.json)
        input2: Model weights file (frozen_inference_graph.pb)
        input3: Model config file (faster_rcnn_resnet50_coco_2018_01_28.pbtxt)
        output1: Output detections filename template with {rank} placeholder
    """
    # Get rank for this parallel instance
    r = faasr_rank()
    rank = r['rank']
    max_rank = r['max_rank']

    faasr_log(f"Starting detect: rank {rank}/{max_rank}")

    # Substitute rank into filenames
    batch_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download batch file
        local_batch = os.path.join(tmpdir, "batch.json")
        faasr_get_file(local_file=local_batch, remote_folder=folder, remote_file=batch_file)

        if not os.path.exists(local_batch) or os.path.getsize(local_batch) == 0:
            faasr_log(f"ERROR: Failed to download batch file {batch_file}")
            raise RuntimeError(f"Batch file {batch_file} not found or empty in S3 folder {folder}")

        faasr_log(f"Downloaded batch: {batch_file}")

        # Download model weights
        local_weights = os.path.join(tmpdir, "frozen_inference_graph.pb")
        faasr_get_file(local_file=local_weights, remote_folder=folder, remote_file=input2)

        if not os.path.exists(local_weights) or os.path.getsize(local_weights) == 0:
            faasr_log(f"ERROR: Failed to download model weights {input2}")
            raise RuntimeError(f"Model weights {input2} not found or empty in S3 folder {folder}")

        faasr_log(f"Downloaded model weights: {input2}")

        # Download model config
        local_config = os.path.join(tmpdir, "model.pbtxt")
        faasr_get_file(local_file=local_config, remote_folder=folder, remote_file=input3)

        if not os.path.exists(local_config) or os.path.getsize(local_config) == 0:
            faasr_log(f"ERROR: Failed to download model config {input3}")
            raise RuntimeError(f"Model config {input3} not found or empty in S3 folder {folder}")

        faasr_log(f"Downloaded model config: {input3}")

        # Load batch data
        with open(local_batch, 'r') as f:
            batch_data = json.load(f)

        frames = batch_data['frames']
        batch_id = batch_data.get('batch_id', rank)

        faasr_log(f"Processing batch {batch_id} with {len(frames)} frames")

        # Load Faster R-CNN model using cv2.dnn.readNetFromTensorflow
        net = cv2.dnn.readNetFromTensorflow(local_weights, local_config)
        faasr_log("Loaded Faster R-CNN model")

        # Process each frame and collect detections
        all_detections = []

        for frame_info in frames:
            frame_index = frame_info['frame_index']
            frame_b64 = frame_info['data']

            # Decode base64 to image
            img_bytes = base64.b64decode(frame_b64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if img is None:
                faasr_log(f"WARNING: Failed to decode frame {frame_index}, skipping")
                continue

            # Create blob from image for Faster R-CNN
            blob = cv2.dnn.blobFromImage(
                img,
                swapRB=True,
                crop=False
            )

            # Set the input and run forward pass
            net.setInput(blob)
            detections = net.forward()

            # Process detections
            # Output shape: [1, 1, num_detections, 7]
            # Each detection: [batch_id, class_id, confidence, x1, y1, x2, y2]
            frame_detection_count = 0
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]

                # Filter by confidence threshold > 0.5
                if confidence > 0.5:
                    class_id = int(detections[0, 0, i, 1])

                    # COCO class IDs are 1-indexed, labels array is 0-indexed
                    if 1 <= class_id <= len(COCO_LABELS):
                        label = COCO_LABELS[class_id - 1]
                    else:
                        label = f"unknown_class_{class_id}"

                    detection_result = {
                        "label": label,
                        "class": class_id,
                        "score": float(confidence)
                    }
                    all_detections.append(detection_result)
                    frame_detection_count += 1

            faasr_log(f"Frame {frame_index}: found {frame_detection_count} detections")

        faasr_log(f"Total detections in batch {batch_id}: {len(all_detections)} (confidence > 0.5)")

        # Write detections to output file
        local_output = os.path.join(tmpdir, "detections.json")
        with open(local_output, 'w') as f:
            json.dump(all_detections, f)

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Uploaded detections: {output_file}")

        faasr_log(f"Detect complete for rank {rank}")
