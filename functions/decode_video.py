import cv2
import numpy as np
import json
import base64
import tempfile
import os


def decode_video(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Downloads video_small.mp4 from S3, decodes exactly F=10 frames,
    splits into N=2 batches of B=5 frames each, serializes each batch
    (frames as numpy arrays) to JSON, and uploads for parallel processing.
    """
    # Parameters from spec
    F = 10  # Total frames to decode
    B = 5   # Batch size
    N = 2   # Number of batches (F/B)

    faasr_log(f"Starting decode_video: extracting {F} frames into {N} batches of {B}")

    # Download video from S3
    with tempfile.TemporaryDirectory() as tmpdir:
        local_video = os.path.join(tmpdir, "video.mp4")
        faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)

        # Check if file was downloaded properly
        if not os.path.exists(local_video) or os.path.getsize(local_video) == 0:
            faasr_log(f"ERROR: Failed to download video file {input1}")
            raise RuntimeError(f"Failed to download video file {input1}")

        faasr_log(f"Downloaded video: {os.path.getsize(local_video)} bytes")

        # Open video with OpenCV
        cap = cv2.VideoCapture(local_video)
        if not cap.isOpened():
            faasr_log(f"ERROR: Could not open video file {input1}")
            raise RuntimeError(f"Could not open video file {input1}")

        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        faasr_log(f"Video has {total_frames} total frames")

        if total_frames < F:
            faasr_log(f"ERROR: Video has {total_frames} frames, need at least {F}")
            raise RuntimeError(f"Video has {total_frames} frames, need at least {F}")

        # Calculate frame indices to extract (evenly spaced through video)
        if total_frames == F:
            frame_indices = list(range(F))
        else:
            # Sample F frames evenly spaced
            frame_indices = [int(i * (total_frames - 1) / (F - 1)) for i in range(F)]

        faasr_log(f"Extracting frames at indices: {frame_indices}")

        # Extract frames
        frames = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                faasr_log(f"ERROR: Failed to read frame at index {idx}")
                raise RuntimeError(f"Failed to read frame at index {idx}")
            frames.append(frame)

        cap.release()
        faasr_log(f"Extracted {len(frames)} frames")

        # Split frames into batches
        batches = []
        for i in range(N):
            start_idx = i * B
            end_idx = start_idx + B
            batch_frames = frames[start_idx:end_idx]
            batches.append(batch_frames)

        # Output files for each batch
        output_files = [output1, output2]

        # Serialize and upload each batch
        for batch_idx, (batch_frames, output_file) in enumerate(zip(batches, output_files)):
            # Serialize frames as base64-encoded numpy arrays
            batch_data = {
                "batch_id": batch_idx + 1,
                "num_frames": len(batch_frames),
                "frames": []
            }

            for frame_idx, frame in enumerate(batch_frames):
                # Encode frame as base64
                frame_bytes = frame.tobytes()
                frame_b64 = base64.b64encode(frame_bytes).decode('ascii')

                frame_info = {
                    "frame_index": frame_idx,
                    "shape": list(frame.shape),
                    "dtype": str(frame.dtype),
                    "data": frame_b64
                }
                batch_data["frames"].append(frame_info)

            # Write to local temp file
            local_batch_file = os.path.join(tmpdir, f"batch_{batch_idx + 1}.json")
            with open(local_batch_file, 'w') as f:
                json.dump(batch_data, f)

            # Upload to S3
            faasr_put_file(local_file=local_batch_file, remote_folder=folder, remote_file=output_file)
            faasr_log(f"Uploaded {output_file} with {len(batch_frames)} frames")

        faasr_log("decode_video completed successfully")
