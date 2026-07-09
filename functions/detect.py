# COCO 80-class label set. The class_id returned by the model is used directly
# as a zero-indexed offset into this list (0 = person), as required.
COCO80 = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


def detect(folder="video_analysis", score_threshold=0.5):
    """
    Map phase of the video-analysis benchmark (one invocation per rank).

    Each of the N parallel invocations:
      1. Reads its rank via faasr_rank() and downloads its batch (batch_<rank>.npy).
      2. Loads the Faster R-CNN ResNet-50 COCO model with cv2.dnn.
      3. Runs detection on every frame in the batch, keeping detections with
         score > 0.5.
      4. Uploads Yi = detections_<rank>.json for the reduce (accumulate) phase.
    """
    import json
    import cv2
    import numpy as np

    # 1. Determine this invocation's rank
    rank_info = faasr_rank()
    rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    batch_file = f"batch_{rank}.npy"
    faasr_get_file(
        remote_folder=f"{folder}/batches",
        remote_file=batch_file,
        local_folder=".",
        local_file=batch_file,
    )

    # 2. Download and load the Faster R-CNN ResNet-50 COCO model (cv2.dnn)
    pb = "frozen_inference_graph.pb"
    pbtxt = "faster_rcnn_resnet50_coco_2018_01_28.pbtxt"
    faasr_get_file(remote_folder=folder, remote_file=pb, local_folder=".", local_file=pb)
    faasr_get_file(remote_folder=folder, remote_file=pbtxt, local_folder=".", local_file=pbtxt)
    net = cv2.dnn.readNetFromTensorflow(pb, pbtxt)

    # 3. Run detection on each frame in the batch
    frames = np.load(batch_file)  # shape (b, H, W, 3), BGR uint8
    detections = []
    for idx in range(frames.shape[0]):
        frame = frames[idx]
        blob = cv2.dnn.blobFromImage(frame, size=(300, 300), swapRB=True, crop=False)
        net.setInput(blob)
        out = net.forward()  # shape (1, 1, num, 7): [_, classId, score, l, t, r, b]

        for i in range(out.shape[2]):
            score = float(out[0, 0, i, 2])
            if score > score_threshold:
                # Use class_id directly as a zero-indexed COCO-80 offset (0 = person)
                class_id = int(out[0, 0, i, 1])
                label = COCO80[class_id] if 0 <= class_id < len(COCO80) else str(class_id)
                detections.append({
                    "label": label,
                    "class": class_id,
                    "score": score,
                })

    # 4. Upload Yi for this rank
    out_file = f"detections_{rank}.json"
    with open(out_file, "w") as f:
        json.dump(detections, f)
    faasr_put_file(
        local_folder=".",
        local_file=out_file,
        remote_folder=f"{folder}/detections",
        remote_file=out_file,
    )

    faasr_log(
        f"detect (rank {rank}/{max_rank}): {len(detections)} detection(s) "
        f"with score > {score_threshold} written to {out_file}"
    )
