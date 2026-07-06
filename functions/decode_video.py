"""
Decode video frames for parallel object detection.

Downloads video from S3, extracts F=10 frames evenly sampled,
partitions into N=2 batches of B=5 frames each, and uploads
each batch as JSON with base64-encoded frame data.
"""

import base64
import json
import os
import tempfile

import cv2


def decode_video(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Decode video and split frames into batches for parallel processing.

    Args:
        folder: S3 remote folder
        input1: Input video filename (video_small.mp4)
        output1: First batch output filename (frame_batch_1.json)
        output2: Second batch output filename (frame_batch_2.json)
    """
    # Constants as specified
    TOTAL_FRAMES = 10  # F = 10 frames
    BATCH_SIZE = 5     # B = 5 frames per batch
    NUM_BATCHES = 2    # N = F/B = 2 batches

    faasr_log(f"Starting decode_video: extracting {TOTAL_FRAMES} frames into {NUM_BATCHES} batches")

    # Create temp directory for processing
    with tempfile.TemporaryDirectory() as tmpdir:
        local_video = os.path.join(tmpdir, input1)

        # Download video from S3
        faasr_log(f"Downloading video: {input1}")
        faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)

        # Verify video file exists and is not empty
        if not os.path.exists(local_video) or os.path.getsize(local_video) == 0:
            faasr_log(f"ERROR: Video file {input1} is missing or empty")
            raise ValueError(f"Video file {input1} is missing or empty - cannot proceed without real video data")

        # Open video with OpenCV
        cap = cv2.VideoCapture(local_video)
        if not cap.isOpened():
            faasr_log(f"ERROR: Failed to open video file {input1}")
            raise ValueError(f"Failed to open video file {input1} - file may be corrupted or invalid format")

        # Get video properties
        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        faasr_log(f"Video info: {total_video_frames} total frames, {fps} fps, {width}x{height}")

        if total_video_frames < TOTAL_FRAMES:
            faasr_log(f"WARNING: Video has only {total_video_frames} frames, using all available")
            frames_to_extract = total_video_frames
        else:
            frames_to_extract = TOTAL_FRAMES

        # Calculate frame indices for even sampling
        if total_video_frames <= frames_to_extract:
            frame_indices = list(range(total_video_frames))
        else:
            # Evenly sample frames across the video
            step = total_video_frames / frames_to_extract
            frame_indices = [int(i * step) for i in range(frames_to_extract)]

        faasr_log(f"Extracting frames at indices: {frame_indices}")

        # Extract frames
        frames = []
        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                faasr_log(f"WARNING: Failed to read frame at index {frame_idx}")
                continue

            # Encode frame to PNG bytes, then base64
            success, encoded = cv2.imencode('.png', frame)
            if not success:
                faasr_log(f"WARNING: Failed to encode frame at index {frame_idx}")
                continue

            frame_b64 = base64.b64encode(encoded.tobytes()).decode('utf-8')
            frames.append({
                "frame_index": frame_idx,
                "data": frame_b64,
                "width": frame.shape[1],
                "height": frame.shape[0]
            })

        cap.release()

        if len(frames) == 0:
            faasr_log("ERROR: No frames could be extracted from video")
            raise ValueError("No frames could be extracted from video - cannot produce output")

        faasr_log(f"Successfully extracted {len(frames)} frames")

        # Partition frames into batches
        # Batch 1: frames 0-4, Batch 2: frames 5-9
        batch1_frames = frames[:BATCH_SIZE]
        batch2_frames = frames[BATCH_SIZE:BATCH_SIZE*2]

        # Handle case where we have fewer frames than expected
        if len(batch2_frames) == 0 and len(batch1_frames) > 0:
            # Split available frames between batches
            mid = len(batch1_frames) // 2
            batch2_frames = batch1_frames[mid:]
            batch1_frames = batch1_frames[:mid]

        # Create batch JSON files
        outputs = [(output1, batch1_frames), (output2, batch2_frames)]

        for i, (output_file, batch_frames) in enumerate(outputs, start=1):
            batch_data = {
                "batch_id": i,
                "total_batches": NUM_BATCHES,
                "frame_count": len(batch_frames),
                "frames": batch_frames
            }

            local_output = os.path.join(tmpdir, output_file)
            with open(local_output, 'w') as f:
                json.dump(batch_data, f)

            faasr_log(f"Uploading batch {i}: {output_file} with {len(batch_frames)} frames")
            faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)

        faasr_log(f"decode_video complete: {len(frames)} frames split into {NUM_BATCHES} batches")
