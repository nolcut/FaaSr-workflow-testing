import cv2
import numpy as np
import tempfile
import os
import json


# COCO 80 class labels (zero-indexed: 0=person, 1=bicycle, 2=car, etc.)
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
    Detect objects in a batch of frames using Faster R-CNN ResNet-50 COCO model.

    Args:
        folder: Remote S3 folder
        input1: Frame batch file (frame_batch_{rank}.npz)
        input2: Model weights file (frozen_inference_graph.pb)
        input3: Model config file (faster_rcnn_resnet50_coco_2018_01_28.pbtxt)
        output1: Output detections file (detections_{rank}.json)
    """
    # Get rank for this parallel instance
    r = faasr_rank()
    rank = r["rank"]
    max_rank = r["max_rank"]

    # Substitute rank placeholder in input/output filenames
    batch_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    faasr_log(f"detect_objects starting: rank {rank}/{max_rank}, processing {batch_file}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download the frame batch file
        local_batch = os.path.join(tmpdir, "frame_batch.npz")
        faasr_get_file(local_file=local_batch, remote_folder=folder, remote_file=batch_file)

        if not os.path.exists(local_batch) or os.path.getsize(local_batch) == 0:
            faasr_log(f"ERROR: Failed to download batch file {batch_file}")
            raise RuntimeError(f"Failed to download batch file {batch_file}")

        faasr_log(f"Downloaded batch file: {os.path.getsize(local_batch)} bytes")

        # Download model files
        local_pb = os.path.join(tmpdir, "frozen_inference_graph.pb")
        local_pbtxt = os.path.join(tmpdir, "model.pbtxt")

        faasr_get_file(local_file=local_pb, remote_folder=folder, remote_file=input2)
        faasr_get_file(local_file=local_pbtxt, remote_folder=folder, remote_file=input3)

        if not os.path.exists(local_pb) or os.path.getsize(local_pb) == 0:
            faasr_log(f"ERROR: Failed to download model weights {input2}")
            raise RuntimeError(f"Failed to download model weights {input2}")

        if not os.path.exists(local_pbtxt) or os.path.getsize(local_pbtxt) == 0:
            faasr_log(f"ERROR: Failed to download model config {input3}")
            raise RuntimeError(f"Failed to download model config {input3}")

        faasr_log(f"Downloaded model files: pb={os.path.getsize(local_pb)} bytes, pbtxt={os.path.getsize(local_pbtxt)} bytes")

        # Load the Faster R-CNN model
        faasr_log("Loading Faster R-CNN model...")
        net = cv2.dnn.readNetFromTensorflow(local_pb, local_pbtxt)
        faasr_log("Model loaded successfully")

        # Load frames from npz
        data = np.load(local_batch)
        num_frames = int(data["num_frames"][0])
        faasr_log(f"Processing {num_frames} frames from batch")

        all_detections = []

        for frame_idx in range(num_frames):
            frame_key = f"frame_{frame_idx}"
            if frame_key not in data:
                faasr_log(f"WARNING: {frame_key} not found in batch")
                continue

            frame = data[frame_key]
            height, width = frame.shape[:2]

            # Preprocess frame for the model
            # Faster R-CNN expects blob with size 300x300 or similar
            blob = cv2.dnn.blobFromImage(
                frame,
                size=(300, 300),
                swapRB=True,
                crop=False
            )

            # Run forward pass
            net.setInput(blob)
            detections_raw = net.forward()

            # Parse detections
            # Output shape: [1, 1, N, 7] where each detection is
            # [batch_id, class_id, confidence, x1, y1, x2, y2]
            for i in range(detections_raw.shape[2]):
                confidence = float(detections_raw[0, 0, i, 2])

                # Filter by confidence threshold > 0.5
                if confidence > 0.5:
                    class_id = int(detections_raw[0, 0, i, 1])

                    # Map class_id to COCO label (zero-indexed)
                    if 0 <= class_id < len(COCO_LABELS):
                        label = COCO_LABELS[class_id]
                    else:
                        label = f"unknown_{class_id}"

                    detection = {
                        "label": label,
                        "class": class_id,
                        "score": round(confidence, 4)
                    }
                    all_detections.append(detection)
                    faasr_log(f"Frame {frame_idx}: detected {label} with score {confidence:.4f}")

        faasr_log(f"Total detections with confidence > 0.5: {len(all_detections)}")

        # Write output JSON
        local_output = os.path.join(tmpdir, "detections.json")
        with open(local_output, "w") as f:
            json.dump(all_detections, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)

        faasr_log(f"detect_objects rank {rank} completed successfully")
