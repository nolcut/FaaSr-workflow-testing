import os
import pickle
import tempfile

import cv2
import numpy as np


def decode_video(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Download video from S3, decode F=10 frames, split into N=2 batches of B=5 frames each.
    Save each batch as a pickle file containing the serialized frame data (numpy arrays).
    """
    # Parameters as specified in the workflow
    F = 10  # Total frames to decode
    B = 5   # Batch size
    N = 2   # Number of batches (F/B)

    faasr_log(f"Starting decode_video: extracting {F} frames into {N} batches of {B}")

    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as tmpdir:
        # Download the video from S3
        local_video = os.path.join(tmpdir, "video.mp4")
        faasr_get_file(local_file=local_video, remote_folder=folder, remote_file=input1)

        # Check if the video file was downloaded successfully
        if not os.path.exists(local_video) or os.path.getsize(local_video) == 0:
            error_msg = f"Failed to download video file '{input1}' from folder '{folder}'"
            faasr_log(error_msg)
            raise RuntimeError(error_msg)

        faasr_log(f"Downloaded video: {input1}")

        # Open the video with OpenCV
        cap = cv2.VideoCapture(local_video)

        if not cap.isOpened():
            error_msg = f"Failed to open video file: {input1}"
            faasr_log(error_msg)
            raise RuntimeError(error_msg)

        # Get video properties
        total_frames_in_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        faasr_log(f"Video has {total_frames_in_video} frames, extracting first {F} frames")

        # Decode exactly F frames
        frames = []
        for i in range(F):
            ret, frame = cap.read()
            if not ret:
                error_msg = f"Failed to read frame {i}. Video may have fewer than {F} frames."
                faasr_log(error_msg)
                raise RuntimeError(error_msg)
            frames.append(frame)

        cap.release()
        faasr_log(f"Decoded {len(frames)} frames successfully")

        # Split frames into batches and save as pickle files
        # batch_1.pkl contains frames 0-4, batch_2.pkl contains frames 5-9
        output_files = [output1, output2]

        for rank in range(1, N + 1):
            start_idx = (rank - 1) * B
            end_idx = start_idx + B
            batch_frames = frames[start_idx:end_idx]

            # Serialize the batch as a list of numpy arrays
            batch_data = {
                "frames": batch_frames,
                "batch_rank": rank,
                "frame_indices": list(range(start_idx, end_idx))
            }

            # Determine output filename
            output_file = output_files[rank - 1]
            local_batch_file = os.path.join(tmpdir, f"batch_{rank}.pkl")

            with open(local_batch_file, "wb") as f:
                pickle.dump(batch_data, f)

            # Upload to S3
            faasr_put_file(local_file=local_batch_file, remote_folder=folder, remote_file=output_file)
            faasr_log(f"Uploaded batch {rank}: {output_file} with frames {start_idx}-{end_idx-1}")

        faasr_log(f"decode_video completed: {N} batches uploaded")
