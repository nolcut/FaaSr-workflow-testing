import os
import json
import base64
import tempfile

import cv2
import numpy as np


# COCO 80 dataset class labels, zero-indexed exactly as used by the spec:
# class_id is used directly (no offset), e.g. class_id 0 = person.
COCO_80_LABELS = [
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

CONF_THRESHOLD = 0.5


def detect_objects(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """Faster R-CNN ResNet-50 COCO object detection for one parallel shard.

    Downloads this instance's batch of decoded frames plus the Faster R-CNN
    model files, loads the model with OpenCV cv2.dnn, and for every frame runs
    a forward pass. Detections with confidence p > 0.5 are recorded as
    {label, class, score} and written to a per-rank output file for downstream
    accumulation.
    """
    r = faasr_rank()
    rank = r["rank"]

    batch_file = input1.format(rank=rank)
    out_file = output1.format(rank=rank)

    workdir = tempfile.mkdtemp(prefix="detect_objects_")
    local_batch = os.path.join(workdir, batch_file)
    local_weights = os.path.join(workdir, input2)
    local_config = os.path.join(workdir, input3)

    # ---- Download this shard's frame batch ----
    faasr_log(f"[rank {rank}] Downloading frame batch '{batch_file}' from folder '{folder}'")
    faasr_get_file(local_file=local_batch, remote_folder=folder, remote_file=batch_file)
    if not os.path.exists(local_batch) or os.path.getsize(local_batch) == 0:
        msg = f"[rank {rank}] Frame batch '{batch_file}' is missing or empty after download"
        faasr_log(f"ERROR: {msg}")
        raise RuntimeError(msg)

    # ---- Download the Faster R-CNN model files ----
    faasr_log(f"[rank {rank}] Downloading model weights '{input2}' and config '{input3}'")
    faasr_get_file(local_file=local_weights, remote_folder=folder, remote_file=input2)
    faasr_get_file(local_file=local_config, remote_folder=folder, remote_file=input3)
    for path, name in ((local_weights, input2), (local_config, input3)):
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            msg = f"[rank {rank}] Model file '{name}' is missing or empty after download"
            faasr_log(f"ERROR: {msg}")
            raise RuntimeError(msg)

    # ---- Parse the batch payload ----
    with open(local_batch, "r") as fh:
        payload = json.load(fh)
    encoded_frames = payload.get("frames", [])
    faasr_log(f"[rank {rank}] Loaded {len(encoded_frames)} frame(s) from '{batch_file}'")

    # ---- Load the Faster R-CNN ResNet-50 COCO model with OpenCV ----
    try:
        net = cv2.dnn.readNetFromTensorflow(local_weights, local_config)
    except cv2.error as exc:
        msg = f"[rank {rank}] cv2.dnn.readNetFromTensorflow failed to load the model: {exc}"
        faasr_log(f"ERROR: {msg}")
        raise RuntimeError(msg)

    # ---- Run detection on every frame in the batch ----
    detections = []
    for idx, enc in enumerate(encoded_frames):
        jpeg_bytes = base64.b64decode(enc)
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            msg = f"[rank {rank}] Failed to decode JPEG for frame index {idx} in '{batch_file}'"
            faasr_log(f"ERROR: {msg}")
            raise RuntimeError(msg)

        blob = cv2.dnn.blobFromImage(img, swapRB=True, crop=False)
        net.setInput(blob)
        out = net.forward()

        # out shape: (1, 1, num_detections, 7)
        # each row: [batchId, classId, confidence, left, top, right, bottom]
        for det in out[0, 0]:
            score = float(det[2])
            if score <= CONF_THRESHOLD:
                continue
            class_id = int(det[1])
            if 0 <= class_id < len(COCO_80_LABELS):
                label = COCO_80_LABELS[class_id]
            else:
                label = "unknown"
            detections.append({"label": label, "class": class_id, "score": score})

    faasr_log(f"[rank {rank}] Found {len(detections)} detection(s) with score > {CONF_THRESHOLD}")

    # ---- Write per-rank detections for downstream accumulation ----
    local_out = os.path.join(workdir, out_file)
    with open(local_out, "w") as fh:
        json.dump(detections, fh)

    faasr_log(f"[rank {rank}] Uploading detections as '{out_file}'")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=out_file)
    faasr_log(f"[rank {rank}] detect_objects complete")
