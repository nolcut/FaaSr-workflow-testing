"""Decode video frames and split into batches for parallel processing."""
import pickle
import os
import cv2
import numpy as np


def decode(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Downloads video, decodes F=10 frames, splits into N=2 batches of B=5 frames each.

    Args:
        folder: S3 folder for input/output
        input1: Input video filename (video_small.mp4)
        output1: Output pickle filename for batch 1 (frame_batch_1.pkl)
        output2: Output pickle filename for batch 2 (frame_batch_2.pkl)
    """
    F = 10  # Total frames to decode
    B = 5   # Batch size
    N = 2   # Number of batches (F/B)

    # Download video from S3
    local_video = "local_video.mp4"
    faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)
    faasr_log(f"Downloaded video: {input1}")

    # Verify video file exists and is not empty
    if not os.path.exists(local_video) or os.path.getsize(local_video) == 0:
        faasr_log(f"ERROR: Video file {input1} is missing or empty")
        raise ValueError(f"Video file {input1} is missing or empty")

    # Open video with OpenCV
    cap = cv2.VideoCapture(local_video)
    if not cap.isOpened():
        faasr_log(f"ERROR: Could not open video file {input1}")
        raise ValueError(f"Could not open video file {input1}")

    # Read exactly F frames
    frames = []
    for i in range(F):
        ret, frame = cap.read()
        if not ret:
            faasr_log(f"ERROR: Could only read {len(frames)} frames, expected {F}")
            cap.release()
            raise ValueError(f"Could only read {len(frames)} frames, expected {F}")
        frames.append(frame)

    cap.release()
    faasr_log(f"Decoded {len(frames)} frames from video")

    # Split frames into batches
    # Batch 1 (rank=1): frames 0-4
    # Batch 2 (rank=2): frames 5-9
    batch1 = frames[0:B]   # frames 0-4
    batch2 = frames[B:F]   # frames 5-9

    # Serialize batches as pickle files containing lists of numpy arrays
    local_batch1 = "batch1.pkl"
    local_batch2 = "batch2.pkl"

    with open(local_batch1, 'wb') as f:
        pickle.dump(batch1, f)
    faasr_log(f"Serialized batch 1 with {len(batch1)} frames")

    with open(local_batch2, 'wb') as f:
        pickle.dump(batch2, f)
    faasr_log(f"Serialized batch 2 with {len(batch2)} frames")

    # Upload batches to S3
    faasr_put_file(local_file=local_batch1, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded {output1}")

    faasr_put_file(local_file=local_batch2, remote_folder=folder, remote_file=output2)
    faasr_log(f"Uploaded {output2}")

    # Clean up local files
    os.remove(local_video)
    os.remove(local_batch1)
    os.remove(local_batch2)

    faasr_log("Decode complete: video split into 2 batches of 5 frames each")
