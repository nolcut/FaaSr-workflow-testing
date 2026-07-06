import os
import json
import base64
import tempfile

import cv2
import numpy as np


def decode_video(folder: str, input1: str, output1: str) -> None:
    """Decode frames from an input video and partition them into rank-numbered
    JSON batches for the downstream parallel `detect_objects` (map) functions.

    F = 10 frames are decoded and split into N = F / B = 2 batches of B = 5
    frames each. Each batch is written as its own JSON file
    (frame_batch_1.json, frame_batch_2.json). Every frame is serialized as a
    base64-encoded JPEG so the downstream detect functions can reconstruct the
    exact image and run Faster R-CNN detection.
    """
    F = 10          # total frames to decode
    B = 5           # batch size
    N = F // B      # number of batches / downstream ranks (2)

    workdir = tempfile.mkdtemp(prefix="decode_video_")
    local_video = os.path.join(workdir, "video_small.mp4")

    # ---- Download the real input video from S3 ----
    faasr_log(f"Downloading input video '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_video) or os.path.getsize(local_video) == 0:
        msg = f"Input video '{input1}' is missing or empty after download"
        faasr_log(f"ERROR: {msg}")
        raise RuntimeError(msg)

    # ---- Decode exactly F frames with OpenCV ----
    cap = cv2.VideoCapture(local_video)
    if not cap.isOpened():
        msg = f"OpenCV could not open the input video '{input1}'"
        faasr_log(f"ERROR: {msg}")
        raise RuntimeError(msg)

    frames = []
    while len(frames) < F:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()

    faasr_log(f"Decoded {len(frames)} frame(s) from '{input1}'")

    if len(frames) < F:
        msg = (
            f"Video '{input1}' yielded only {len(frames)} decodable frame(s); "
            f"F = {F} frames are required to form {N} batches of B = {B}"
        )
        faasr_log(f"ERROR: {msg}")
        raise RuntimeError(msg)

    # ---- Serialize frames as base64-encoded JPEGs ----
    encoded_frames = []
    for idx, frame in enumerate(frames):
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            msg = f"Failed to JPEG-encode decoded frame index {idx}"
            faasr_log(f"ERROR: {msg}")
            raise RuntimeError(msg)
        encoded_frames.append(base64.b64encode(buf.tobytes()).decode("ascii"))

    # ---- Partition into N batches of size B and upload one file per rank ----
    for rank in range(1, N + 1):
        start = (rank - 1) * B
        batch = encoded_frames[start:start + B]

        batch_payload = {
            "batch_index": rank,
            "batch_size": len(batch),
            "encoding": "base64_jpeg",
            "frames": batch,
        }

        remote_file = output1.replace("{rank}", str(rank))
        local_batch = os.path.join(workdir, remote_file)
        with open(local_batch, "w") as fh:
            json.dump(batch_payload, fh)

        faasr_log(
            f"Uploading batch {rank}/{N} with {len(batch)} frame(s) as '{remote_file}'"
        )
        faasr_put_file(
            local_file=local_batch, remote_folder=folder, remote_file=remote_file
        )

    faasr_log(f"decode_video complete: produced {N} frame batches")
