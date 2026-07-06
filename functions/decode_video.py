import base64
import json
import os
import tempfile

import cv2
import numpy as np


def decode_video(folder: str, input1: str, output1: str) -> None:
    """
    Download video file from S3, decode exactly F=10 frames using OpenCV.
    Partition into N=2 batches of size B=5 frames each.
    Batch 1 contains frames 0-4, Batch 2 contains frames 5-9.
    Each batch is serialized with base64-encoded frame data for downstream processing.
    """
    TOTAL_FRAMES = 10
    BATCH_SIZE = 5
    NUM_BATCHES = TOTAL_FRAMES // BATCH_SIZE  # 2

    faasr_log(f"Starting decode_video: downloading {input1}")

    # Download video file from S3
    with tempfile.TemporaryDirectory() as tmpdir:
        local_video = os.path.join(tmpdir, "video.mp4")
        faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)

        # Verify the video file was downloaded and is not empty
        if not os.path.exists(local_video) or os.path.getsize(local_video) == 0:
            faasr_log(f"ERROR: Failed to download video file {input1} or file is empty")
            raise RuntimeError(f"Failed to download video file {input1} or file is empty")

        faasr_log(f"Video file downloaded: {os.path.getsize(local_video)} bytes")

        # Open video with OpenCV
        cap = cv2.VideoCapture(local_video)
        if not cap.isOpened():
            faasr_log(f"ERROR: Cannot open video file {input1}")
            raise RuntimeError(f"Cannot open video file {input1}")

        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        faasr_log(f"Video has {total_video_frames} total frames, extracting {TOTAL_FRAMES} frames")

        # Calculate frame indices to extract (evenly spaced if video has more frames)
        if total_video_frames >= TOTAL_FRAMES:
            # Evenly sample TOTAL_FRAMES frames from the video
            frame_indices = [int(i * total_video_frames / TOTAL_FRAMES) for i in range(TOTAL_FRAMES)]
        else:
            # If video has fewer frames, use what we have (may need to repeat or error)
            faasr_log(f"WARNING: Video has only {total_video_frames} frames, need {TOTAL_FRAMES}")
            frame_indices = list(range(total_video_frames))
            # Repeat last frame if needed
            while len(frame_indices) < TOTAL_FRAMES:
                frame_indices.append(frame_indices[-1] if frame_indices else 0)

        # Decode frames
        frames = []
        for idx, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                faasr_log(f"ERROR: Failed to read frame at index {frame_idx}")
                raise RuntimeError(f"Failed to read frame at index {frame_idx}")
            frames.append(frame)
            faasr_log(f"Decoded frame {idx}: shape={frame.shape}")

        cap.release()

        faasr_log(f"Decoded {len(frames)} frames, creating {NUM_BATCHES} batches of {BATCH_SIZE} each")

        # Create batches and upload
        for batch_num in range(1, NUM_BATCHES + 1):
            start_idx = (batch_num - 1) * BATCH_SIZE
            end_idx = start_idx + BATCH_SIZE
            batch_frames = frames[start_idx:end_idx]

            # Serialize batch: each frame as base64-encoded numpy array with metadata
            batch_data = {
                "batch_num": batch_num,
                "total_batches": NUM_BATCHES,
                "frame_indices": list(range(start_idx, end_idx)),
                "frames": []
            }

            for i, frame in enumerate(batch_frames):
                frame_info = {
                    "frame_idx": start_idx + i,
                    "shape": list(frame.shape),
                    "dtype": str(frame.dtype),
                    "data": base64.b64encode(frame.tobytes()).decode("ascii")
                }
                batch_data["frames"].append(frame_info)

            # Write batch to local file
            local_batch_file = os.path.join(tmpdir, f"frame_batch_{batch_num}.json")
            with open(local_batch_file, "w") as f:
                json.dump(batch_data, f)

            # Upload batch file to S3
            remote_batch_file = output1.replace("{rank}", str(batch_num))
            faasr_put_file(local_file=local_batch_file, remote_folder=folder, remote_file=remote_batch_file)
            faasr_log(f"Uploaded batch {batch_num} as {remote_batch_file}")

    faasr_log(f"decode_video completed: {NUM_BATCHES} batches uploaded")
