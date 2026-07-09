"""
FaaSr Video Analysis benchmark -- Decode stage.

Downloads the input video from the S3 ``video_analysis/`` folder, decodes the
first ``num_frames`` (F) frames, splits them into ``num_ranks`` (N = F / B)
batches of size ``batch_size`` (B) and uploads one ``batch_<rank>.npz`` per
batch. The N batches are consumed by the N parallel ``detect_objects``
invocations that follow in the map phase.
"""

import cv2
import numpy as np
from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_invocation_id,
    faasr_log,
    faasr_put_file,
)


def _work_folder(input_folder: str) -> str:
    """Per-invocation folder used to isolate intermediate artifacts."""
    return f"{input_folder}/{faasr_invocation_id()}"


def decode_video(
    input_folder: str = "video_analysis",
    video_file: str = "video_small.mp4",
    num_frames: int = 10,
    batch_size: int = 5,
    num_ranks: int = 2,
) -> None:
    """
    Decode F frames from the input video and upload N = F / B batches of size B.

    Args:
        input_folder: S3 folder that holds the external inputs (the video).
        video_file: Name of the input video in ``input_folder``.
        num_frames: Number of frames F to decode from the video.
        batch_size: Number of frames B per batch.
        num_ranks: Number of batches N (should equal F / B).
    """
    # 1. Download the input video from the shared input folder.
    faasr_get_file(
        remote_folder=input_folder,
        remote_file=video_file,
        local_file=video_file,
    )
    faasr_log(f"Downloaded video {input_folder}/{video_file}")

    # 2. Decode the first `num_frames` frames.
    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file {video_file}")

    frames = []
    while len(frames) < num_frames:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)  # BGR frame as read by OpenCV
    cap.release()

    if not frames:
        raise RuntimeError("No frames could be decoded from the video")
    faasr_log(f"Decoded {len(frames)} frames (requested {num_frames})")

    # 3. Split the frames into N batches of size B and upload each batch.
    work_folder = _work_folder(input_folder)
    total = len(frames)
    for rank in range(1, num_ranks + 1):
        start = (rank - 1) * batch_size
        end = min(start + batch_size, total)
        batch = frames[start:end]

        batch_file = f"batch_{rank}.npz"
        # object dtype keeps per-frame arrays even if shapes ever differ.
        np.savez_compressed(batch_file, frames=np.array(batch, dtype=object))
        faasr_put_file(
            local_file=batch_file,
            remote_folder=work_folder,
            remote_file=batch_file,
        )
        faasr_log(
            f"Uploaded {batch_file} with {len(batch)} frames "
            f"(frames {start}..{end - 1}) to {work_folder}"
        )

    faasr_log(
        f"Decode complete: {total} frames -> {num_ranks} batches of size "
        f"{batch_size} in {work_folder}"
    )
