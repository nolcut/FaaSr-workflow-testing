import json

import cv2
import numpy as np
from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_log,
    faasr_put_file,
    faasr_rank,
)

# COCO 80-class label set, indexed directly by the model's class_id
# (zero-indexed, no offset). e.g. COCO_CLASSES[0] == "person".
COCO_CLASSES = [
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


def label_for_class(class_id):
    """Map a zero-indexed COCO class_id directly to its label."""
    if 0 <= class_id < len(COCO_CLASSES):
        return COCO_CLASSES[class_id]
    return f"unknown_{class_id}"


def detect(
    folder="video_analysis",
    batch_size=5,
    score_threshold=0.5,
    model_weights="frozen_inference_graph.pb",
    model_config="faster_rcnn_resnet50_coco_2018_01_28.pbtxt",
):
    """
    One of the N parallel map-phase workers.

    Each invocation is assigned a unique rank in [1..N] via faasr_rank().
    Rank r downloads batch_r.npy (produced by ``decode``), applies the
    Faster R-CNN ResNet-50 COCO model (loaded with cv2.dnn), and keeps all
    detections with confidence p > ``score_threshold`` (0.5). The resulting
    Yi is uploaded as detections_r.json for the accumulator to gather.
    """
    rank_info = faasr_rank()
    rank = rank_info["rank"]
    max_rank = rank_info["max_rank"]
    faasr_log(f"detect: rank {rank} of {max_rank}")

    # 1. Download the Faster R-CNN model files (weights + config).
    faasr_get_file(
        remote_folder=folder, remote_file=model_weights, local_file=model_weights
    )
    faasr_get_file(
        remote_folder=folder, remote_file=model_config, local_file=model_config
    )
    faasr_log("detect: downloaded Faster R-CNN ResNet-50 COCO model files")

    # 2. Load the model with OpenCV's DNN module.
    net = cv2.dnn.readNetFromTensorflow(model_weights, model_config)

    # 3. Download this rank's batch of frames.
    batch_file = f"batch_{rank}.npy"
    ids_file = f"batch_{rank}_frame_ids.npy"
    faasr_get_file(remote_folder=folder, remote_file=batch_file, local_file=batch_file)
    faasr_get_file(remote_folder=folder, remote_file=ids_file, local_file=ids_file)

    frames = np.load(batch_file)
    frame_ids = np.load(ids_file)
    faasr_log(f"detect: rank {rank} loaded {len(frames)} frame(s) from {batch_file}")

    # 4. Run detection on each frame and keep detections with score > 0.5.
    detections = []
    for local_idx, frame in enumerate(frames):
        frame_id = int(frame_ids[local_idx])
        h, w = frame.shape[:2]

        blob = cv2.dnn.blobFromImage(frame, swapRB=True, crop=False)
        net.setInput(blob)
        out = net.forward()  # shape: (1, 1, num_detections, 7)

        for det in out[0, 0]:
            score = float(det[2])
            if score <= score_threshold:
                continue
            # det = [imageId, classId, confidence, left, top, right, bottom]
            class_id = int(det[1])  # zero-indexed COCO class, used directly
            detections.append(
                {
                    "frame": frame_id,
                    "label": label_for_class(class_id),
                    "class": class_id,
                    "score": score,
                }
            )

    faasr_log(
        f"detect: rank {rank} produced {len(detections)} detection(s) "
        f"with score > {score_threshold}"
    )

    # 5. Upload Yi for this rank.
    out_file = f"detections_{rank}.json"
    with open(out_file, "w") as f:
        json.dump(detections, f)

    faasr_put_file(local_file=out_file, remote_folder=folder, remote_file=out_file)
    faasr_log(f"detect: rank {rank} uploaded {folder}/{out_file}")
