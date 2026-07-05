"""
detect_objects: Applies Faster R-CNN ResNet-50 COCO model to a batch of decoded
video frames for object detection. Uses OpenCV's DNN module to load and run
the TensorFlow model. Filters detections to keep only those with confidence > 0.5.
For each kept detection, extracts class_id (zero-indexed), maps it to COCO 80-class
label, and records {label, class, score}.
"""

import base64
import json
import os
import tempfile

import cv2
import numpy as np


# COCO 80-class labels (zero-indexed: 0=person, 1=bicycle, ...)
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


def detect_objects(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """
    Applies Faster R-CNN ResNet-50 COCO model to a batch of decoded video frames.

    Args:
        folder: S3 folder name
        input1: Batch file template (batch_{rank}.json)
        input2: Frozen inference graph file (frozen_inference_graph.pb)
        input3: Model config file (faster_rcnn_resnet50_coco_2018_01_28.pbtxt)
        output1: Output detections file template (batch_detections_{rank}.json)
    """
    # Get rank info for parallel execution
    r = faasr_rank()
    rank = r['rank']

    # Substitute rank in filenames
    batch_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    faasr_log(f"Starting object detection for rank {rank}: processing {batch_file}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download required files
        local_batch = os.path.join(tmpdir, batch_file)
        local_model = os.path.join(tmpdir, input2)
        local_config = os.path.join(tmpdir, input3)

        faasr_get_file(local_file=local_batch, remote_folder=folder, remote_file=batch_file)
        faasr_get_file(local_file=local_model, remote_folder=folder, remote_file=input2)
        faasr_get_file(local_file=local_config, remote_folder=folder, remote_file=input3)

        # Verify batch file was downloaded
        if not os.path.exists(local_batch) or os.path.getsize(local_batch) == 0:
            faasr_log(f"ERROR: Failed to download batch file {batch_file}")
            raise RuntimeError(f"Failed to download batch file {batch_file}")

        # Verify model files exist
        if not os.path.exists(local_model) or os.path.getsize(local_model) == 0:
            faasr_log(f"ERROR: Failed to download model file {input2}")
            raise RuntimeError(f"Failed to download model file {input2}")

        if not os.path.exists(local_config) or os.path.getsize(local_config) == 0:
            faasr_log(f"ERROR: Failed to download config file {input3}")
            raise RuntimeError(f"Failed to download config file {input3}")

        faasr_log(f"Downloaded files: batch={os.path.getsize(local_batch)} bytes, "
                  f"model={os.path.getsize(local_model)} bytes, "
                  f"config={os.path.getsize(local_config)} bytes")

        # Load batch data
        with open(local_batch, 'r') as f:
            batch_data = json.load(f)

        frames = batch_data.get('frames', [])
        faasr_log(f"Loaded batch with {len(frames)} frames")

        # Load the Faster R-CNN model using OpenCV DNN
        net = cv2.dnn.readNetFromTensorflow(local_model, local_config)
        faasr_log("Loaded Faster R-CNN model")

        # Process each frame
        all_detections = []

        for frame_info in frames:
            frame_index = frame_info.get('frame_index', -1)
            b64_data = frame_info.get('data', '')

            if not b64_data:
                faasr_log(f"Warning: Empty frame data at index {frame_index}")
                continue

            # Decode base64 JPEG to numpy array
            img_bytes = base64.b64decode(b64_data)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if frame is None:
                faasr_log(f"Warning: Failed to decode frame at index {frame_index}")
                continue

            height, width = frame.shape[:2]

            # Prepare input blob for the network
            # Faster R-CNN expects BGR input, no mean subtraction, scale 1.0
            blob = cv2.dnn.blobFromImage(frame, scalefactor=1.0, size=(width, height),
                                         mean=(0, 0, 0), swapRB=False, crop=False)

            # Run inference
            net.setInput(blob)
            detections = net.forward()

            # Process detections
            # Output shape is typically (1, 1, N, 7) where each detection has:
            # [batch_id, class_id, confidence, left, top, right, bottom]
            frame_detections = []

            for i in range(detections.shape[2]):
                confidence = float(detections[0, 0, i, 2])

                # Filter by confidence threshold > 0.5
                if confidence > 0.5:
                    # class_id from detection (1-indexed in TF model output, convert to 0-indexed)
                    class_id_raw = int(detections[0, 0, i, 1])
                    # TensorFlow COCO models output 1-indexed class IDs, subtract 1 for 0-indexed
                    class_id = class_id_raw - 1

                    # Map to COCO label (handle out-of-range)
                    if 0 <= class_id < len(COCO_LABELS):
                        label = COCO_LABELS[class_id]
                    else:
                        label = f"unknown_{class_id}"

                    detection_record = {
                        "label": label,
                        "class": class_id,
                        "score": round(confidence, 4)
                    }
                    frame_detections.append(detection_record)

            faasr_log(f"Frame {frame_index}: {len(frame_detections)} detections with score > 0.5")
            all_detections.extend(frame_detections)

        faasr_log(f"Total detections for batch: {len(all_detections)}")

        # Save detections to output file
        output_data = all_detections

        local_output = os.path.join(tmpdir, output_file)
        with open(local_output, 'w') as f:
            json.dump(output_data, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)

        faasr_log(f"Uploaded {output_file} to S3")
        faasr_log(f"Object detection complete for rank {rank}")
