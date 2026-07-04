import cv2
import numpy as np
import tempfile
import os


def decode_video(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Decode video and extract F=10 frames evenly sampled, split into N=2 batches of B=5 each.

    Args:
        folder: Remote S3 folder
        input1: Input video file (video_small.mp4)
        output1: First batch output file (frame_batch_1.npz)
        output2: Second batch output file (frame_batch_2.npz)
    """
    F = 10  # Total frames to extract
    B = 5   # Batch size
    N = 2   # Number of batches (F/B)

    faasr_log(f"Starting decode_video: extracting {F} frames into {N} batches of {B} each")

    # Download the video file
    with tempfile.TemporaryDirectory() as tmpdir:
        local_video = os.path.join(tmpdir, "video.mp4")
        faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)

        # Check if video was downloaded successfully
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
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        faasr_log(f"Video properties: {total_frames} frames, {fps} fps, {width}x{height}")

        if total_frames < F:
            faasr_log(f"WARNING: Video has only {total_frames} frames, extracting all available")
            F = total_frames

        # Calculate frame indices for even sampling
        # Evenly sample F frames from the video
        if total_frames == F:
            frame_indices = list(range(F))
        else:
            frame_indices = [int(i * (total_frames - 1) / (F - 1)) for i in range(F)]

        faasr_log(f"Sampling frames at indices: {frame_indices}")

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
        faasr_log(f"Successfully extracted {len(frames)} frames")

        # Split into batches and save
        output_files = [output1, output2]

        for batch_idx in range(N):
            start = batch_idx * B
            end = start + B
            batch_frames = frames[start:end]

            # Create npz file with frames
            # Store each frame with a key like 'frame_0', 'frame_1', etc.
            local_batch = os.path.join(tmpdir, f"batch_{batch_idx + 1}.npz")

            # Save frames as a dict with frame indices
            frame_dict = {f"frame_{i}": batch_frames[i] for i in range(len(batch_frames))}
            frame_dict["num_frames"] = np.array([len(batch_frames)])

            np.savez(local_batch, **frame_dict)

            faasr_log(f"Saved batch {batch_idx + 1} with {len(batch_frames)} frames to {output_files[batch_idx]}")

            # Upload to S3
            faasr_put_file(local_file=local_batch, remote_folder=folder, remote_file=output_files[batch_idx])

        faasr_log("decode_video completed successfully")
