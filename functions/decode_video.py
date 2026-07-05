"""
decode_video: Downloads video, decodes F=10 frames evenly sampled,
partitions into N=2 batches of B=5 frames each.
Outputs batch_1.json (frames 0-4) and batch_2.json (frames 5-9).
Each batch contains base64-encoded JPEG frames.
"""

import base64
import json
import os
import tempfile

import cv2


def decode_video(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Downloads video file from S3, decodes exactly 10 frames evenly sampled,
    and partitions them into 2 batches of 5 frames each.

    Args:
        folder: S3 folder name
        input1: Input video filename (small_video.mp4)
        output1: First batch output filename (batch_1.json)
        output2: Second batch output filename (batch_2.json)
    """
    F = 10  # Total frames to extract
    B = 5   # Batch size
    N = 2   # Number of batches

    faasr_log(f"Starting video decode: {input1}")

    # Download video from S3 to a temporary file
    with tempfile.TemporaryDirectory() as tmpdir:
        local_video = os.path.join(tmpdir, "video.mp4")
        faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)

        # Verify the video file was downloaded and has content
        if not os.path.exists(local_video) or os.path.getsize(local_video) == 0:
            faasr_log(f"ERROR: Failed to download video file {input1}")
            raise RuntimeError(f"Failed to download video file {input1}")

        faasr_log(f"Downloaded video file: {os.path.getsize(local_video)} bytes")

        # Open video with OpenCV
        cap = cv2.VideoCapture(local_video)
        if not cap.isOpened():
            faasr_log(f"ERROR: Could not open video file {input1}")
            raise RuntimeError(f"Could not open video file {input1}")

        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        faasr_log(f"Video has {total_frames} frames at {fps} fps")

        if total_frames < F:
            faasr_log(f"Warning: Video has fewer frames ({total_frames}) than requested ({F})")
            # Adjust F to available frames if needed
            actual_F = min(F, total_frames)
        else:
            actual_F = F

        # Calculate frame indices for even sampling
        # We want F frames evenly distributed across the video
        if total_frames == 1:
            frame_indices = [0] * actual_F
        elif actual_F == 1:
            frame_indices = [0]
        else:
            # Evenly sample F frames from 0 to total_frames-1
            frame_indices = [
                int(i * (total_frames - 1) / (actual_F - 1))
                for i in range(actual_F)
            ]

        faasr_log(f"Extracting frames at indices: {frame_indices}")

        # Extract frames
        frames_data = []
        for idx, frame_num in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()

            if not ret:
                faasr_log(f"ERROR: Failed to read frame {frame_num}")
                raise RuntimeError(f"Failed to read frame {frame_num}")

            # Encode frame as JPEG
            success, encoded = cv2.imencode('.jpg', frame)
            if not success:
                faasr_log(f"ERROR: Failed to encode frame {frame_num} as JPEG")
                raise RuntimeError(f"Failed to encode frame {frame_num} as JPEG")

            # Convert to base64
            b64_frame = base64.b64encode(encoded.tobytes()).decode('utf-8')

            frames_data.append({
                "frame_index": idx,
                "original_frame_num": frame_num,
                "data": b64_frame
            })

        cap.release()
        faasr_log(f"Extracted {len(frames_data)} frames")

        # Pad with last frame if we got fewer than F frames
        while len(frames_data) < F:
            frames_data.append(frames_data[-1].copy())
            frames_data[-1]["frame_index"] = len(frames_data) - 1

        # Split into batches
        # Batch 1: frames 0-4 (indices 0 to B-1)
        # Batch 2: frames 5-9 (indices B to F-1)
        batch_1_frames = frames_data[0:B]  # frames 0-4
        batch_2_frames = frames_data[B:F]  # frames 5-9

        # Create batch JSON files
        batch_1_json = {
            "batch_id": 1,
            "total_batches": N,
            "frames": batch_1_frames
        }

        batch_2_json = {
            "batch_id": 2,
            "total_batches": N,
            "frames": batch_2_frames
        }

        # Write batch files locally
        local_batch_1 = os.path.join(tmpdir, "batch_1.json")
        local_batch_2 = os.path.join(tmpdir, "batch_2.json")

        with open(local_batch_1, 'w') as f:
            json.dump(batch_1_json, f)
        faasr_log(f"Created batch 1 with {len(batch_1_frames)} frames")

        with open(local_batch_2, 'w') as f:
            json.dump(batch_2_json, f)
        faasr_log(f"Created batch 2 with {len(batch_2_frames)} frames")

        # Upload batches to S3
        # The output filenames are batch_1.json and batch_2.json
        # For the ranked successor detect_objects (x2), we write exactly 2 shards
        faasr_put_file(local_file=local_batch_1, remote_folder=folder, remote_file=output1)
        faasr_put_file(local_file=local_batch_2, remote_folder=folder, remote_file=output2)

        faasr_log(f"Uploaded {output1} and {output2} to S3")
        faasr_log("Video decode complete")
