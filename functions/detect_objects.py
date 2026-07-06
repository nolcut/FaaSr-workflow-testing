import base64
import json
import os
import tempfile

import cv2
import numpy as np


# COCO 80 class labels (zero-indexed: 0=person, 1=bicycle, etc.)
# This is the standard COCO 80-class dataset ordering
COCO_80_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane",
    "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird",
    "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat",
    "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut",
    "cake", "chair", "couch", "potted plant", "bed",
    "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven",
    "toaster", "sink", "refrigerator", "book", "clock",
    "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]


def detect_objects(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """
    Load Faster R-CNN ResNet-50 COCO model and run object detection on a batch of frames.

    Args:
        folder: Remote folder name
        input1: Frame batch JSON file (contains base64-encoded frames)
        input2: Frozen inference graph (.pb file)
        input3: Model configuration file (.pbtxt file)
        output1: Output detections JSON file
    """
    # Get rank info for parallel execution
    r = faasr_rank()
    rank = r['rank']

    faasr_log(f"Starting detect_objects for rank {rank}")

    # Substitute rank placeholder in input/output names
    input_batch_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download frame batch
        local_batch_file = os.path.join(tmpdir, "frame_batch.json")
        faasr_get_file(local_file=local_batch_file, remote_folder=folder, remote_file=input_batch_file)

        if not os.path.exists(local_batch_file) or os.path.getsize(local_batch_file) == 0:
            faasr_log(f"ERROR: Failed to download frame batch {input_batch_file} or file is empty")
            raise RuntimeError(f"Failed to download frame batch {input_batch_file} or file is empty")

        faasr_log(f"Downloaded frame batch: {input_batch_file}")

        # Download model files
        local_pb_file = os.path.join(tmpdir, "frozen_inference_graph.pb")
        local_pbtxt_file = os.path.join(tmpdir, "model.pbtxt")

        faasr_get_file(local_file=local_pb_file, remote_folder=folder, remote_file=input2)
        faasr_get_file(local_file=local_pbtxt_file, remote_folder=folder, remote_file=input3)

        if not os.path.exists(local_pb_file) or os.path.getsize(local_pb_file) == 0:
            faasr_log(f"ERROR: Failed to download model file {input2} or file is empty")
            raise RuntimeError(f"Failed to download model file {input2} or file is empty")

        if not os.path.exists(local_pbtxt_file) or os.path.getsize(local_pbtxt_file) == 0:
            faasr_log(f"ERROR: Failed to download model config {input3} or file is empty")
            raise RuntimeError(f"Failed to download model config {input3} or file is empty")

        faasr_log(f"Downloaded model files: {input2}, {input3}")

        # Load the Faster R-CNN model using OpenCV DNN
        net = cv2.dnn.readNetFromTensorflow(local_pb_file, local_pbtxt_file)
        faasr_log("Loaded Faster R-CNN model")

        # Load frame batch data
        with open(local_batch_file, "r") as f:
            batch_data = json.load(f)

        batch_num = batch_data["batch_num"]
        frames_data = batch_data["frames"]
        faasr_log(f"Processing batch {batch_num} with {len(frames_data)} frames")

        all_detections = []

        # Process each frame in the batch
        for frame_info in frames_data:
            frame_idx = frame_info["frame_idx"]
            shape = tuple(frame_info["shape"])
            dtype = np.dtype(frame_info["dtype"])

            # Decode the base64 frame data
            frame_bytes = base64.b64decode(frame_info["data"])
            frame = np.frombuffer(frame_bytes, dtype=dtype).reshape(shape)

            faasr_log(f"Processing frame {frame_idx}, shape={shape}")

            # Prepare the frame for the model (create a blob)
            # Faster R-CNN expects BGR input, no mean subtraction, scale factor 1.0
            blob = cv2.dnn.blobFromImage(frame, size=(300, 300), swapRB=False, crop=False)

            # Run inference
            net.setInput(blob)
            detections = net.forward()

            # Parse detections
            # Output shape is typically (1, 1, N, 7) where N is number of detections
            # Each detection: [batch_id, class_id, confidence, x1, y1, x2, y2]
            frame_detections = []

            for i in range(detections.shape[2]):
                confidence = float(detections[0, 0, i, 2])

                # Filter by confidence threshold > 0.5
                if confidence > 0.5:
                    class_id = int(detections[0, 0, i, 1])

                    # The COCO model class_id is 1-indexed (1-90 range mapping to 80 classes)
                    # We need to convert to zero-indexed COCO 80 labels
                    # The mapping: model outputs class_ids 1-90 which map to COCO labels
                    # For simplicity, we use the direct zero-indexed approach as specified:
                    # "class_id directly (zero-indexed, no offset; e.g. 0=person)"
                    # The model's class_id needs to be converted to 0-based index
                    zero_indexed_class = class_id - 1  # Convert 1-indexed to 0-indexed

                    if 0 <= zero_indexed_class < len(COCO_80_LABELS):
                        label = COCO_80_LABELS[zero_indexed_class]
                    else:
                        label = f"unknown_class_{class_id}"

                    detection_record = {
                        "label": label,
                        "class": zero_indexed_class,
                        "score": confidence
                    }
                    frame_detections.append(detection_record)
                    faasr_log(f"Frame {frame_idx}: Detected {label} (class {zero_indexed_class}) with score {confidence:.3f}")

            all_detections.append({
                "frame_idx": frame_idx,
                "detections": frame_detections
            })

        # Prepare output
        output_data = {
            "rank": rank,
            "batch_num": batch_num,
            "total_frames": len(frames_data),
            "frame_detections": all_detections
        }

        # Count total detections
        total_detections = sum(len(fd["detections"]) for fd in all_detections)
        faasr_log(f"Total detections for rank {rank}: {total_detections}")

        # Write output
        local_output_file = os.path.join(tmpdir, "detections.json")
        with open(local_output_file, "w") as f:
            json.dump(output_data, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output_file, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Uploaded detections to {output_file}")

    faasr_log(f"detect_objects completed for rank {rank}")
