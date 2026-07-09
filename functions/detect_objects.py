"""
FaaSr Video Analysis benchmark -- Detect (map) stage.

Runs as ``num_ranks`` parallel invocations (the map phase). Each invocation
uses its rank to pick a single ``batch_<rank>.npz`` produced by the decode
stage, applies the Faster R-CNN ResNet-50 COCO model (loaded with OpenCV
``cv2.dnn``) to every frame in the batch, and keeps every detection with
confidence score > ``score_threshold`` (0.5). The per-rank result Yi is
written to ``detections_<rank>.json`` for the accumulate stage.
"""

import json

import cv2
import numpy as np
from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_invocation_id,
    faasr_log,
    faasr_put_file,
    faasr_rank,
)

# COCO 80 labels, zero-indexed. The class_id returned by the model is used
# directly as an index into this list (no offset): class_id 0 -> "person".
COCO80_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


def _work_folder(input_folder: str) -> str:
    return f"{input_folder}/{faasr_invocation_id()}"


def _label_for(class_id: int) -> str:
    """Map a zero-indexed COCO 80 class_id directly to its label."""
    if 0 <= class_id < len(COCO80_LABELS):
        return COCO80_LABELS[class_id]
    return f"unknown_{class_id}"


def detect_objects(
    input_folder: str = "video_analysis",
    batch_size: int = 5,
    score_threshold: float = 0.5,
    pb_file: str = "frozen_inference_graph.pb",
    pbtxt_file: str = "faster_rcnn_resnet50_coco_2018_01_28.pbtxt",
) -> None:
    """
    Detect objects in this rank's batch of frames using Faster R-CNN.

    Args:
        input_folder: S3 folder holding the external inputs (the model files).
        batch_size: Number of frames B per batch (informational).
        score_threshold: Minimum confidence p to keep a detection (0.5).
        pb_file: Frozen inference graph filename.
        pbtxt_file: Text graph (config) filename for cv2.dnn.
    """
    # 1. Determine which batch this invocation is responsible for.
    rank_data = faasr_rank()
    rank = rank_data["rank"]
    max_rank = rank_data["max_rank"]
    faasr_log(f"Detect rank {rank} of {max_rank}")

    work_folder = _work_folder(input_folder)

    # 2. Download this rank's batch of frames.
    batch_file = f"batch_{rank}.npz"
    faasr_get_file(
        remote_folder=work_folder,
        remote_file=batch_file,
        local_file=batch_file,
    )
    data = np.load(batch_file, allow_pickle=True)
    frames = list(data["frames"])
    faasr_log(f"Loaded {len(frames)} frames from {batch_file}")

    # 3. Download and load the Faster R-CNN ResNet-50 COCO model.
    faasr_get_file(
        remote_folder=input_folder, remote_file=pb_file, local_file=pb_file
    )
    faasr_get_file(
        remote_folder=input_folder, remote_file=pbtxt_file, local_file=pbtxt_file
    )
    net = cv2.dnn.readNetFromTensorflow(pb_file, pbtxt_file)
    faasr_log("Loaded Faster R-CNN ResNet-50 COCO model with cv2.dnn")

    # 4. Run detection on every frame in the batch, keeping score > threshold.
    detections = []
    for frame_idx, frame in enumerate(frames):
        frame = np.ascontiguousarray(frame)
        blob = cv2.dnn.blobFromImage(frame, swapRB=True, crop=False)
        net.setInput(blob)
        out = net.forward()

        # out shape: [1, 1, N, 7] -> [image_id, class_id, score, x1, y1, x2, y2]
        for det in out[0, 0]:
            score = float(det[2])
            if score <= score_threshold:
                continue
            class_id = int(det[1])
            detections.append(
                {
                    "label": _label_for(class_id),
                    "class": class_id,
                    "score": score,
                }
            )

        faasr_log(f"Frame {frame_idx}: cumulative detections = {len(detections)}")

    # 5. Persist this rank's result Yi.
    out_file = f"detections_{rank}.json"
    with open(out_file, "w") as f:
        json.dump(detections, f)
    faasr_put_file(
        local_file=out_file, remote_folder=work_folder, remote_file=out_file
    )
    faasr_log(
        f"Detect rank {rank}: kept {len(detections)} detections "
        f"(score > {score_threshold}) -> {work_folder}/{out_file}"
    )
