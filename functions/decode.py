import base64
import json
import os
import tempfile

import cv2
import numpy as np


def decode(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Downloads video_small.mp4 from S3, decodes exactly F=10 frames,
    and partitions them into N=2 batches of size B=5 frames each.

    Batch 1 (frames 0-4) -> output1 (frame_batch_1.json)
    Batch 2 (frames 5-9) -> output2 (frame_batch_2.json)
    """
    F = 10  # Total frames to extract
    B = 5   # Batch size
    N = 2   # Number of batches (F/B)

    # Download the video file
    faasr_log(f"Downloading video file: {input1}")
    local_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)

    # Verify video file exists and has content
    if not os.path.exists(local_video) or os.path.getsize(local_video) == 0:
        faasr_log(f"ERROR: Failed to download video file {input1} or file is empty")
        raise RuntimeError(f"Failed to download video file {input1}")

    faasr_log(f"Opening video file for frame extraction")
    cap = cv2.VideoCapture(local_video)

    if not cap.isOpened():
        faasr_log(f"ERROR: Could not open video file {local_video}")
        os.unlink(local_video)
        raise RuntimeError(f"Could not open video file {input1}")

    # Extract exactly F frames
    frames = []
    frame_count = 0

    while frame_count < F:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
        frame_count += 1

    cap.release()
    os.unlink(local_video)

    if len(frames) < F:
        faasr_log(f"ERROR: Video has only {len(frames)} frames, expected at least {F}")
        raise RuntimeError(f"Video has only {len(frames)} frames, expected at least {F}")

    faasr_log(f"Extracted {len(frames)} frames from video")

    # Convert frames to base64-encoded PNG images
    def frame_to_base64(frame):
        """Encode a single frame as base64 PNG."""
        success, encoded = cv2.imencode('.png', frame)
        if not success:
            raise RuntimeError("Failed to encode frame to PNG")
        return base64.b64encode(encoded.tobytes()).decode('utf-8')

    # Create batch 1: frames 0-4
    batch1_frames = []
    for i in range(B):  # frames 0-4
        batch1_frames.append({
            "frame_index": i,
            "image_base64": frame_to_base64(frames[i])
        })

    # Create batch 2: frames 5-9
    batch2_frames = []
    for i in range(B, F):  # frames 5-9
        batch2_frames.append({
            "frame_index": i,
            "image_base64": frame_to_base64(frames[i])
        })

    # Save batch 1
    batch1_data = {
        "batch_id": 1,
        "frames": batch1_frames,
        "frame_indices": list(range(0, B)),
        "total_frames": F
    }

    local_batch1 = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w').name
    with open(local_batch1, 'w') as f:
        json.dump(batch1_data, f)

    faasr_log(f"Uploading batch 1 with frames 0-4: {output1}")
    faasr_put_file(local_file=local_batch1, remote_folder=folder, remote_file=output1)
    os.unlink(local_batch1)

    # Save batch 2
    batch2_data = {
        "batch_id": 2,
        "frames": batch2_frames,
        "frame_indices": list(range(B, F)),
        "total_frames": F
    }

    local_batch2 = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w').name
    with open(local_batch2, 'w') as f:
        json.dump(batch2_data, f)

    faasr_log(f"Uploading batch 2 with frames 5-9: {output2}")
    faasr_put_file(local_file=local_batch2, remote_folder=folder, remote_file=output2)
    os.unlink(local_batch2)

    faasr_log(f"Decode complete: created {N} batches of {B} frames each")
