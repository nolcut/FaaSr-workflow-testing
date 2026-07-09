import cv2
import numpy as np
from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_log,
    faasr_put_file,
)


def decode(
    folder="video_analysis",
    video_file="video_small.mp4",
    num_frames=10,
    batch_size=5,
    num_batches=2,
):
    """
    Map-phase producer for the video-analysis benchmark.

    Steps:
      1. Download the input video from S3 (video_analysis/).
      2. Decode the first F = ``num_frames`` frames.
      3. Split the frames into N = F / B batches of size B = ``batch_size``.
      4. Upload each batch as batch_<rank>.npy so that the N parallel
         ``detect`` invocations (rank 1..N) can each pick up one batch.

    With F = 10 and B = 5 this yields N = 2 batches -> two parallel detect
    functions in the map phase.
    """
    # 1. Download the input video.
    faasr_get_file(
        remote_folder=folder,
        remote_file=video_file,
        local_file=video_file,
    )
    faasr_log(f"decode: downloaded video {folder}/{video_file}")

    # 2. Decode up to F frames.
    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        raise RuntimeError(f"decode: could not open video {video_file}")

    frames = []
    while len(frames) < num_frames:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()

    decoded = len(frames)
    faasr_log(f"decode: decoded {decoded} frame(s) (requested F={num_frames})")

    if decoded == 0:
        raise RuntimeError("decode: no frames could be decoded from the video")

    # 3. Split into N = F / B batches of size B.
    #    Compute N from the frames we actually have so the map fan-out stays
    #    consistent even if the video has fewer frames than requested.
    n_batches = max(1, decoded // batch_size)
    if decoded % batch_size != 0:
        # Keep any trailing frames in the last batch.
        n_batches = (decoded + batch_size - 1) // batch_size

    # 4. Upload N batches. Detect ranks are 1-indexed (rank 1..N), so batch
    #    files are named batch_1.npy .. batch_N.npy to match faasr_rank().
    for i in range(n_batches):
        start = i * batch_size
        end = min(start + batch_size, decoded)
        batch = frames[start:end]
        rank = i + 1

        # Stack the batch frames (all frames share the same H x W x 3 shape)
        # and remember the absolute frame indices for downstream traceability.
        arr = np.stack(batch, axis=0)
        frame_ids = np.arange(start, end)

        local_batch = f"batch_{rank}.npy"
        local_ids = f"batch_{rank}_frame_ids.npy"
        np.save(local_batch, arr)
        np.save(local_ids, frame_ids)

        faasr_put_file(
            local_file=local_batch,
            remote_folder=folder,
            remote_file=local_batch,
        )
        faasr_put_file(
            local_file=local_ids,
            remote_folder=folder,
            remote_file=local_ids,
        )
        faasr_log(
            f"decode: uploaded {local_batch} "
            f"(rank {rank}/{n_batches}, frames {start}..{end - 1})"
        )

    faasr_log(
        f"decode: produced N={n_batches} batch(es) of size B={batch_size} "
        f"-> {n_batches} parallel detect function(s)"
    )
