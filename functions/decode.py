import pickle
import tempfile
import os

import cv2
import numpy as np


def decode(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Downloads video, decodes F=10 frames, and uploads N=2 batches of B=5 frames each.
    Each batch is pickled as a list of numpy arrays for downstream detect functions.
    """
    F = 10  # Total number of frames to extract
    B = 5   # Batch size
    N = F // B  # Number of batches (2)

    # Download the video file from S3
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, input1)
        faasr_get_file(local_file=video_path, remote_folder=folder, remote_file=input1)

        # Verify the file was downloaded and is not empty
        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            faasr_log(f"ERROR: Failed to download video file {input1} or file is empty")
            raise RuntimeError(f"Failed to download video file {input1} from S3 folder {folder}")

        # Open the video with OpenCV
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            faasr_log(f"ERROR: Cannot open video file {input1}")
            raise RuntimeError(f"Cannot open video file {input1}")

        # Get total frame count
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        faasr_log(f"Video has {total_frames} total frames")

        if total_frames == 0:
            faasr_log("ERROR: Video has no frames")
            cap.release()
            raise RuntimeError(f"Video file {input1} has no frames")

        # Calculate frame indices to sample evenly
        if total_frames >= F:
            # Evenly sample F frames across the video
            frame_indices = np.linspace(0, total_frames - 1, F, dtype=int).tolist()
        else:
            # If video has fewer than F frames, use all available frames
            frame_indices = list(range(total_frames))
            faasr_log(f"WARNING: Video has only {total_frames} frames, using all")

        faasr_log(f"Sampling {len(frame_indices)} frames at indices: {frame_indices}")

        # Extract frames
        frames = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
            else:
                faasr_log(f"WARNING: Could not read frame at index {idx}")

        cap.release()

        if len(frames) == 0:
            faasr_log("ERROR: Could not extract any frames from video")
            raise RuntimeError("Could not extract any frames from video")

        faasr_log(f"Extracted {len(frames)} frames")

        # Split frames into batches and upload
        # batch 1: frames 0-4 (indices 0..B-1)
        # batch 2: frames 5-9 (indices B..2B-1)
        output_files = [output1, output2]

        for i in range(N):
            start_idx = i * B
            end_idx = min((i + 1) * B, len(frames))
            batch_frames = frames[start_idx:end_idx]

            if len(batch_frames) == 0:
                faasr_log(f"WARNING: Batch {i+1} is empty, skipping")
                continue

            # Pickle the batch of frames (list of numpy arrays)
            batch_path = os.path.join(tmpdir, f"batch_{i+1}.pkl")
            with open(batch_path, "wb") as f:
                pickle.dump(batch_frames, f)

            # Upload the batch file
            # The output file pattern uses {rank} placeholder for ranked successor
            # output1 = "frame_batch_1.pkl", output2 = "frame_batch_2.pkl"
            output_file = output_files[i]
            faasr_put_file(local_file=batch_path, remote_folder=folder, remote_file=output_file)
            faasr_log(f"Uploaded batch {i+1} with {len(batch_frames)} frames to {output_file}")

    faasr_log(f"decode complete: processed {len(frames)} frames into {N} batches")
