import base64
import json
import os
import tempfile

import cv2
import numpy as np


# COCO 80 dataset labels (zero-indexed, no offset)
COCO_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]


def detect(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """
    Loads Faster R-CNN ResNet-50 COCO model using OpenCV cv2.dnn from frozen_inference_graph.pb
    and faster_rcnn_resnet50_coco_2018_01_28.pbtxt files. Reads the batch of decoded frames
    assigned to this ranked instance. For each frame, runs object detection through the neural
    network, extracting bounding boxes, class IDs, and confidence scores. Filters detections
    to keep only those with confidence score > 0.5. Maps each class_id directly to COCO 80
    dataset labels (zero-indexed, no offset; e.g. class_id 0 = person).
    """
    # Get rank for this instance
    r = faasr_rank()
    rank = r['rank']

    faasr_log(f"Starting detect function for rank {rank}")

    # Substitute rank placeholder in input/output filenames
    batch_file = input1.format(rank=rank)
    model_weights = input2  # frozen_inference_graph.pb
    model_config = input3   # faster_rcnn_resnet50_coco_2018_01_28.pbtxt
    output_file = output1.format(rank=rank)

    # Download the batch file
    local_batch = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    faasr_log(f"Downloading batch file: {batch_file}")
    faasr_get_file(local_file=local_batch, remote_folder=folder, remote_file=batch_file)

    # Verify batch file exists and has content
    if not os.path.exists(local_batch) or os.path.getsize(local_batch) == 0:
        faasr_log(f"ERROR: Failed to download batch file {batch_file} or file is empty")
        raise RuntimeError(f"Failed to download batch file {batch_file}")

    # Load the batch data
    with open(local_batch, 'r') as f:
        batch_data = json.load(f)
    os.unlink(local_batch)

    frames = batch_data.get('frames', [])
    if not frames:
        faasr_log(f"ERROR: No frames found in batch file {batch_file}")
        raise RuntimeError(f"No frames found in batch file {batch_file}")

    faasr_log(f"Loaded {len(frames)} frames from batch {batch_data.get('batch_id', rank)}")

    # Download model files
    local_weights = tempfile.NamedTemporaryFile(suffix=".pb", delete=False).name
    local_config = tempfile.NamedTemporaryFile(suffix=".pbtxt", delete=False).name

    faasr_log(f"Downloading model weights: {model_weights}")
    faasr_get_file(local_file=local_weights, remote_folder=folder, remote_file=model_weights)

    faasr_log(f"Downloading model config: {model_config}")
    faasr_get_file(local_file=local_config, remote_folder=folder, remote_file=model_config)

    # Verify model files exist and have content
    if not os.path.exists(local_weights) or os.path.getsize(local_weights) == 0:
        faasr_log(f"ERROR: Failed to download model weights {model_weights} or file is empty")
        os.unlink(local_weights)
        os.unlink(local_config)
        raise RuntimeError(f"Failed to download model weights {model_weights}")

    if not os.path.exists(local_config) or os.path.getsize(local_config) == 0:
        faasr_log(f"ERROR: Failed to download model config {model_config} or file is empty")
        os.unlink(local_weights)
        os.unlink(local_config)
        raise RuntimeError(f"Failed to download model config {model_config}")

    # Load the Faster R-CNN model using OpenCV DNN
    faasr_log("Loading Faster R-CNN model with OpenCV DNN")
    net = cv2.dnn.readNetFromTensorflow(local_weights, local_config)

    # Clean up model files
    os.unlink(local_weights)
    os.unlink(local_config)

    # Process each frame
    all_detections = []

    for frame_data in frames:
        frame_index = frame_data['frame_index']
        image_base64 = frame_data['image_base64']

        # Decode the base64 image
        image_bytes = base64.b64decode(image_base64)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            faasr_log(f"WARNING: Failed to decode frame {frame_index}, skipping")
            continue

        rows, cols, _ = frame.shape

        # Create blob from image for network input
        blob = cv2.dnn.blobFromImage(frame, swapRB=True, crop=False)
        net.setInput(blob)

        # Run forward pass
        detections_output = net.forward()

        frame_detections = []

        # detections_output shape is typically [1, 1, N, 7] where each detection has:
        # [batch_id, class_id, confidence, left, top, right, bottom]
        for i in range(detections_output.shape[2]):
            detection = detections_output[0, 0, i]
            confidence = float(detection[2])

            # Filter by confidence threshold > 0.5
            if confidence > 0.5:
                class_id = int(detection[1])

                # Map class_id directly to COCO 80 labels (zero-indexed, no offset)
                # Ensure class_id is within valid range
                if 0 <= class_id < len(COCO_LABELS):
                    label = COCO_LABELS[class_id]
                else:
                    label = f"unknown_class_{class_id}"

                frame_detections.append({
                    "label": label,
                    "class": class_id,
                    "score": round(confidence, 4)
                })

        all_detections.append({
            "frame_index": frame_index,
            "detections": frame_detections
        })

        faasr_log(f"Frame {frame_index}: found {len(frame_detections)} detections with confidence > 0.5")

    # Prepare output data
    output_data = {
        "batch_id": batch_data.get('batch_id', rank),
        "rank": rank,
        "total_frames_processed": len(all_detections),
        "frame_detections": all_detections
    }

    # Save and upload results
    local_output = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w').name
    with open(local_output, 'w') as f:
        json.dump(output_data, f, indent=2)

    faasr_log(f"Uploading detection results: {output_file}")
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)
    os.unlink(local_output)

    total_detections = sum(len(fd['detections']) for fd in all_detections)
    faasr_log(f"Detect complete for rank {rank}: processed {len(all_detections)} frames, found {total_detections} total detections with confidence > 0.5")
