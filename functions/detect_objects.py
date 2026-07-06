"""
Detect objects in video frames using Faster R-CNN ResNet-50 COCO model.

Uses OpenCV cv2.dnn to load the model from frozen_inference_graph.pb
and faster_rcnn_resnet50_coco_2018_01_28.pbtxt. For each frame in the
assigned batch (based on rank), runs object detection and filters
detections to keep only those with confidence > 0.5.
"""

import base64
import json
import os
import tempfile

import cv2
import numpy as np


# COCO 80 class labels (zero-indexed, as specified in the user request)
# Mapping: index 0 = person, index 1 = bicycle, etc.
COCO_80_LABELS = [
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

# Mapping from TensorFlow model class IDs (1-90 with gaps) to COCO 80 zero-indexed labels
# TensorFlow COCO model uses COCO 91 category IDs where some IDs are skipped
# This maps model class_id -> (coco_80_index, label)
COCO_91_TO_80 = {
    1: 0,    # person
    2: 1,    # bicycle
    3: 2,    # car
    4: 3,    # motorcycle
    5: 4,    # airplane
    6: 5,    # bus
    7: 6,    # train
    8: 7,    # truck
    9: 8,    # boat
    10: 9,   # traffic light
    11: 10,  # fire hydrant
    13: 11,  # stop sign
    14: 12,  # parking meter
    15: 13,  # bench
    16: 14,  # bird
    17: 15,  # cat
    18: 16,  # dog
    19: 17,  # horse
    20: 18,  # sheep
    21: 19,  # cow
    22: 20,  # elephant
    23: 21,  # bear
    24: 22,  # zebra
    25: 23,  # giraffe
    27: 24,  # backpack
    28: 25,  # umbrella
    31: 26,  # handbag
    32: 27,  # tie
    33: 28,  # suitcase
    34: 29,  # frisbee
    35: 30,  # skis
    36: 31,  # snowboard
    37: 32,  # sports ball
    38: 33,  # kite
    39: 34,  # baseball bat
    40: 35,  # baseball glove
    41: 36,  # skateboard
    42: 37,  # surfboard
    43: 38,  # tennis racket
    44: 39,  # bottle
    46: 40,  # wine glass
    47: 41,  # cup
    48: 42,  # fork
    49: 43,  # knife
    50: 44,  # spoon
    51: 45,  # bowl
    52: 46,  # banana
    53: 47,  # apple
    54: 48,  # sandwich
    55: 49,  # orange
    56: 50,  # broccoli
    57: 51,  # carrot
    58: 52,  # hot dog
    59: 53,  # pizza
    60: 54,  # donut
    61: 55,  # cake
    62: 56,  # chair
    63: 57,  # couch
    64: 58,  # potted plant
    65: 59,  # bed
    67: 60,  # dining table
    70: 61,  # toilet
    72: 62,  # tv
    73: 63,  # laptop
    74: 64,  # mouse
    75: 65,  # remote
    76: 66,  # keyboard
    77: 67,  # cell phone
    78: 68,  # microwave
    79: 69,  # oven
    80: 70,  # toaster
    81: 71,  # sink
    82: 72,  # refrigerator
    84: 73,  # book
    85: 74,  # clock
    86: 75,  # vase
    87: 76,  # scissors
    88: 77,  # teddy bear
    89: 78,  # hair drier
    90: 79,  # toothbrush
}


def detect_objects(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """
    Detect objects in video frames using Faster R-CNN.

    Args:
        folder: S3 remote folder
        input1: Batch of frames JSON file (frame_batch_{rank}.json)
        input2: Model weights file (frozen_inference_graph.pb)
        input3: Model config file (faster_rcnn_resnet50_coco_2018_01_28.pbtxt)
        output1: Output detections JSON file (detections_{rank}.json)
    """
    # Get rank for parallel execution
    r = faasr_rank()
    rank = r['rank']
    max_rank = r['max_rank']

    faasr_log(f"Starting detect_objects: rank {rank} of {max_rank}")

    # Substitute rank placeholder in filenames
    batch_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download the batch of frames
        local_batch = os.path.join(tmpdir, batch_file)
        faasr_log(f"Downloading batch file: {batch_file}")
        faasr_get_file(local_file=local_batch, remote_folder=folder, remote_file=batch_file)

        # Verify batch file exists and is not empty
        if not os.path.exists(local_batch) or os.path.getsize(local_batch) == 0:
            faasr_log(f"ERROR: Batch file {batch_file} is missing or empty")
            raise ValueError(f"Batch file {batch_file} is missing or empty - cannot proceed without real frame data")

        # Download model weights
        local_weights = os.path.join(tmpdir, input2)
        faasr_log(f"Downloading model weights: {input2}")
        faasr_get_file(local_file=local_weights, remote_folder=folder, remote_file=input2)

        # Verify weights file
        if not os.path.exists(local_weights) or os.path.getsize(local_weights) == 0:
            faasr_log(f"ERROR: Model weights file {input2} is missing or empty")
            raise ValueError(f"Model weights file {input2} is missing or empty - cannot proceed without model")

        # Download model config
        local_config = os.path.join(tmpdir, input3)
        faasr_log(f"Downloading model config: {input3}")
        faasr_get_file(local_file=local_config, remote_folder=folder, remote_file=input3)

        # Verify config file
        if not os.path.exists(local_config) or os.path.getsize(local_config) == 0:
            faasr_log(f"ERROR: Model config file {input3} is missing or empty")
            raise ValueError(f"Model config file {input3} is missing or empty - cannot proceed without model")

        # Load the Faster R-CNN model using OpenCV DNN
        faasr_log("Loading Faster R-CNN model with OpenCV DNN")
        net = cv2.dnn.readNetFromTensorflow(local_weights, local_config)

        # Load the batch of frames
        with open(local_batch, 'r') as f:
            batch_data = json.load(f)

        batch_id = batch_data.get('batch_id', rank)
        frames = batch_data.get('frames', [])

        if not frames:
            faasr_log(f"ERROR: No frames found in batch file {batch_file}")
            raise ValueError(f"No frames found in batch file {batch_file} - cannot proceed without frame data")

        faasr_log(f"Processing batch {batch_id} with {len(frames)} frames")

        # Process each frame and collect detections
        all_detections = []
        confidence_threshold = 0.5

        for frame_info in frames:
            frame_index = frame_info.get('frame_index', 0)
            frame_b64 = frame_info.get('data', '')

            if not frame_b64:
                faasr_log(f"WARNING: Empty frame data at index {frame_index}")
                continue

            # Decode base64 PNG to numpy array
            frame_bytes = base64.b64decode(frame_b64)
            frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame is None:
                faasr_log(f"WARNING: Failed to decode frame at index {frame_index}")
                continue

            height, width = frame.shape[:2]

            # Create blob from image for Faster R-CNN
            blob = cv2.dnn.blobFromImage(frame, swapRB=True, crop=False)

            # Run inference
            net.setInput(blob)
            detections = net.forward()

            # Process detections
            # Faster R-CNN output shape: (1, 1, N, 7)
            # Each detection: [batch_id, class_id, confidence, x1, y1, x2, y2]
            for i in range(detections.shape[2]):
                confidence = float(detections[0, 0, i, 2])

                # Filter by confidence threshold > 0.5
                if confidence > confidence_threshold:
                    model_class_id = int(detections[0, 0, i, 1])

                    # Map model class_id (1-90 with gaps) to COCO 80 index (0-79)
                    # as specified: zero-indexed, no offset (0=person)
                    if model_class_id in COCO_91_TO_80:
                        coco_class_id = COCO_91_TO_80[model_class_id]
                        label = COCO_80_LABELS[coco_class_id]
                    else:
                        # Handle unknown class IDs (shouldn't happen with valid COCO model)
                        coco_class_id = model_class_id - 1
                        label = f"unknown_class_{model_class_id}"

                    detection_entry = {
                        "label": label,
                        "class": coco_class_id,
                        "score": round(confidence, 4),
                        "frame_index": frame_index
                    }
                    all_detections.append(detection_entry)

            faasr_log(f"Frame {frame_index}: found {sum(1 for d in all_detections if d.get('frame_index') == frame_index)} detections with score > 0.5")

        # Create output JSON
        output_data = {
            "batch_id": batch_id,
            "rank": rank,
            "detection_count": len(all_detections),
            "detections": all_detections
        }

        # Write output file
        local_output = os.path.join(tmpdir, output_file)
        with open(local_output, 'w') as f:
            json.dump(output_data, f, indent=2)

        # Upload to S3
        faasr_log(f"Uploading detections: {output_file} with {len(all_detections)} detections")
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)

        faasr_log(f"detect_objects complete: batch {batch_id}, {len(all_detections)} total detections with score > 0.5")
