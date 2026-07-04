"""Detect objects in video frames using Faster R-CNN ResNet-50 COCO model."""
import json
import os
import pickle

import cv2
import numpy as np


def detect(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """
    Loads Faster R-CNN model and detects objects in a batch of frames.

    Args:
        folder: S3 folder for input/output
        input1: Input pickle filename pattern (frame_batch_{rank}.pkl)
        input2: Model weights file (frozen_inference_graph.pb)
        input3: Model config file (faster_rcnn_resnet50_coco_2018_01_28.pbtxt)
        output1: Output JSON filename pattern (detections_batch_{rank}.json)
    """
    # Get rank for this parallel instance
    r = faasr_rank()
    rank = r['rank']
    faasr_log(f"Starting detect for rank {rank} of {r['max_rank']}")

    # Substitute rank into filenames
    input_frames = input1.format(rank=rank)
    output_detections = output1.format(rank=rank)

    # Download frame batch from S3
    local_frames = "local_frames.pkl"
    faasr_get_file(local_file=local_frames, remote_folder=folder, remote_file=input_frames)
    faasr_log(f"Downloaded frame batch: {input_frames}")

    # Verify frame file exists and is not empty
    if not os.path.exists(local_frames) or os.path.getsize(local_frames) == 0:
        faasr_log(f"ERROR: Frame batch file {input_frames} is missing or empty")
        raise ValueError(f"Frame batch file {input_frames} is missing or empty")

    # Load frames from pickle
    with open(local_frames, 'rb') as f:
        frames = pickle.load(f)
    faasr_log(f"Loaded {len(frames)} frames from batch")

    # Download model weights
    local_weights = "frozen_inference_graph.pb"
    faasr_get_file(local_file=local_weights, remote_folder=folder, remote_file=input2)
    faasr_log(f"Downloaded model weights: {input2}")

    # Verify weights file exists and is not empty
    if not os.path.exists(local_weights) or os.path.getsize(local_weights) == 0:
        faasr_log(f"ERROR: Model weights file {input2} is missing or empty")
        raise ValueError(f"Model weights file {input2} is missing or empty")

    # Download model config
    local_config = "model_config.pbtxt"
    faasr_get_file(local_file=local_config, remote_folder=folder, remote_file=input3)
    faasr_log(f"Downloaded model config: {input3}")

    # Verify config file exists and is not empty
    if not os.path.exists(local_config) or os.path.getsize(local_config) == 0:
        faasr_log(f"ERROR: Model config file {input3} is missing or empty")
        raise ValueError(f"Model config file {input3} is missing or empty")

    # Load Faster R-CNN model using OpenCV's dnn module
    net = cv2.dnn.readNetFromTensorflow(local_weights, local_config)
    faasr_log("Loaded Faster R-CNN model")

    # Confidence threshold
    CONFIDENCE_THRESHOLD = 0.5

    # Process each frame and collect detections
    all_detections = []

    for frame_idx, frame in enumerate(frames):
        # Create blob from image
        # Faster R-CNN expects BGR input, which OpenCV provides by default
        blob = cv2.dnn.blobFromImage(frame, swapRB=True, crop=False)

        # Set input and run forward pass
        net.setInput(blob)
        detections = net.forward()

        # detections shape is typically (1, 1, num_detections, 7)
        # where each detection is [batch_id, class_id, confidence, left, top, right, bottom]
        num_detections = detections.shape[2]

        for i in range(num_detections):
            detection = detections[0, 0, i]
            confidence = float(detection[2])

            # Filter by confidence threshold
            if confidence > CONFIDENCE_THRESHOLD:
                class_id = int(detection[1])
                all_detections.append({
                    "class": class_id,
                    "score": confidence
                })

        faasr_log(f"Processed frame {frame_idx + 1}/{len(frames)}")

    faasr_log(f"Found {len(all_detections)} detections with confidence > {CONFIDENCE_THRESHOLD}")

    # Write detections to JSON
    local_output = "detections.json"
    with open(local_output, 'w') as f:
        json.dump(all_detections, f)

    # Upload to S3
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_detections)
    faasr_log(f"Uploaded {output_detections}")

    # Clean up local files
    os.remove(local_frames)
    os.remove(local_weights)
    os.remove(local_config)
    os.remove(local_output)

    faasr_log(f"Detect complete for rank {rank}: {len(all_detections)} detections")
