"""
Decode function for video analysis workflow.

Downloads video_small.mp4 from S3, decodes F=10 frames evenly sampled from the video,
splits into N=2 batches of size B=5 each. Each batch is serialized as JSON with
base64-encoded frame data and frame indices.
"""

import base64
import json
import os
import tempfile

import cv2
import numpy as np


def decode(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """
    Decode video frames and create batches for parallel processing.

    Args:
        folder: S3 folder name
        input1: Input video filename (video_small.mp4)
        input2: Model weights file (frozen_inference_graph.pb) - passed through
        input3: Model config file (faster_rcnn_resnet50_coco_2018_01_28.pbtxt) - passed through
        output1: Output batch filename template with {rank} placeholder
    """
    # Constants as specified
    F = 10  # Total frames to extract
    B = 5   # Batch size
    N = 2   # Number of batches (F/B)

    faasr_log(f"Starting decode: extracting {F} frames into {N} batches of {B}")

    # Create temp directory for local processing
    with tempfile.TemporaryDirectory() as tmpdir:
        # Download video from S3
        local_video = os.path.join(tmpdir, "video.mp4")
        faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)

        # Check if video file was downloaded properly
        if not os.path.exists(local_video) or os.path.getsize(local_video) == 0:
            faasr_log(f"ERROR: Failed to download video file {input1}")
            raise RuntimeError(f"Video file {input1} not found or empty in S3 folder {folder}")

        faasr_log(f"Downloaded video: {input1}")

        # Open video with OpenCV
        cap = cv2.VideoCapture(local_video)
        if not cap.isOpened():
            faasr_log(f"ERROR: Cannot open video file {input1}")
            raise RuntimeError(f"Cannot open video file {input1}")

        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        faasr_log(f"Video properties: {total_frames} frames, {fps:.2f} fps, {width}x{height}")

        if total_frames < F:
            faasr_log(f"WARNING: Video has only {total_frames} frames, extracting all available")
            F = total_frames

        # Calculate frame indices to extract (evenly sampled)
        if total_frames == F:
            frame_indices = list(range(F))
        else:
            # Evenly sample F frames from the video
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

            # Encode frame as PNG bytes, then base64
            success, encoded = cv2.imencode('.png', frame)
            if not success:
                faasr_log(f"ERROR: Failed to encode frame at index {idx}")
                raise RuntimeError(f"Failed to encode frame at index {idx}")

            frame_b64 = base64.b64encode(encoded.tobytes()).decode('utf-8')
            frames.append({
                'frame_index': idx,
                'data': frame_b64
            })

        cap.release()
        faasr_log(f"Extracted {len(frames)} frames")

        # Split frames into batches and upload
        for batch_num in range(1, N + 1):
            start_idx = (batch_num - 1) * B
            end_idx = min(batch_num * B, len(frames))
            batch_frames = frames[start_idx:end_idx]

            batch_data = {
                'batch_id': batch_num,
                'total_batches': N,
                'frames': batch_frames,
                'video_info': {
                    'source': input1,
                    'total_frames': total_frames,
                    'fps': fps,
                    'width': width,
                    'height': height
                }
            }

            # Write batch to local file
            local_batch = os.path.join(tmpdir, f"batch_{batch_num}.json")
            with open(local_batch, 'w') as f:
                json.dump(batch_data, f)

            # Upload to S3
            remote_batch = output1.replace("{rank}", str(batch_num))
            faasr_put_file(local_file=local_batch, remote_folder=folder, remote_file=remote_batch)
            faasr_log(f"Uploaded batch {batch_num}: {remote_batch} with {len(batch_frames)} frames")

        faasr_log("Decode complete")
