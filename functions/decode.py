def decode(folder="video_analysis", video_file="video_small.mp4", F=10, B=5):
    """
    Decode phase of the video-analysis benchmark.

    1. Downloads the input video (video_small.mp4) from the video_analysis/ folder.
    2. Decodes the first F frames.
    3. Splits the frames into N = ceil(F / B) batches of size B and uploads each
       batch so that N parallel `detect` functions can process them.

    With F = 10 and B = 5 this produces N = 2 batches -> two parallel detect ranks.
    """
    import math
    import cv2
    import numpy as np

    # 1. Download the input video from S3 (video_analysis/ folder)
    faasr_get_file(
        remote_folder=folder,
        remote_file=video_file,
        local_folder=".",
        local_file=video_file,
    )

    # 2. Decode up to F frames
    cap = cv2.VideoCapture(video_file)
    frames = []
    while len(frames) < F:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    F_actual = len(frames)
    if F_actual == 0:
        raise RuntimeError(f"decode: no frames could be read from {video_file}")

    # 3. Split into N = ceil(F / B) batches of size B and upload each batch
    N = math.ceil(F_actual / B)
    for i in range(N):
        batch = frames[i * B:(i + 1) * B]
        arr = np.stack(batch, axis=0)  # shape (b, H, W, 3), BGR uint8
        local_file = f"batch_{i + 1}.npy"
        np.save(local_file, arr)
        faasr_put_file(
            local_folder=".",
            local_file=local_file,
            remote_folder=f"{folder}/batches",
            remote_file=local_file,
        )
        faasr_log(f"decode: uploaded {local_file} with {arr.shape[0]} frames")

    faasr_log(
        f"decode: decoded {F_actual} frames into {N} batch(es) of size {B}; "
        f"triggering {N} parallel detect invocation(s)"
    )
