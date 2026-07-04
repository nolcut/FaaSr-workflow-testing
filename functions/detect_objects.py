import cv2
import numpy as np
import json
import base64
import tempfile
import os


def detect_objects(folder: str, input1: str, input2: str, input3: str, output1: str) -> None:
    """
    Loads Faster R-CNN ResNet-50 COCO model and performs object detection on a batch of frames.
    Filters detections to keep only those with confidence score > 0.5.
    """
    # COCO labels (0-indexed list, class_id is 1-indexed so use class_id-1)
    labels = [
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
        "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
        "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
        "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
        "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
        "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
        "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
        "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
        "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
        "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
        "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
        "toothbrush"
    ]

    # Get rank for parallel execution
    r = faasr_rank()
    rank = r['rank']

    # Substitute rank placeholder in filenames
    batch_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    faasr_log(f"detect_objects rank {rank}: processing batch {batch_file}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download model files
        local_weights = os.path.join(tmpdir, "model.pb")
        local_config = os.path.join(tmpdir, "model.pbtxt")
        local_batch = os.path.join(tmpdir, "batch.json")

        # Get model weights
        faasr_get_file(local_file=local_weights, remote_folder=folder, remote_file=input2)
        if not os.path.exists(local_weights) or os.path.getsize(local_weights) == 0:
            faasr_log(f"ERROR: Failed to download model weights {input2}")
            raise RuntimeError(f"Failed to download model weights {input2}")

        # Get model config
        faasr_get_file(local_file=local_config, remote_folder=folder, remote_file=input3)
        if not os.path.exists(local_config) or os.path.getsize(local_config) == 0:
            faasr_log(f"ERROR: Failed to download model config {input3}")
            raise RuntimeError(f"Failed to download model config {input3}")

        faasr_log(f"Downloaded model files: weights={os.path.getsize(local_weights)} bytes, config={os.path.getsize(local_config)} bytes")

        # Load the Faster R-CNN model
        try:
            net = cv2.dnn.readNetFromTensorflow(local_weights, local_config)
        except cv2.error as e:
            faasr_log(f"ERROR: Failed to load model: {e}")
            raise RuntimeError(f"Failed to load Faster R-CNN model: {e}")

        faasr_log("Loaded Faster R-CNN ResNet-50 COCO model")

        # Download batch file
        faasr_get_file(local_file=local_batch, remote_folder=folder, remote_file=batch_file)
        if not os.path.exists(local_batch) or os.path.getsize(local_batch) == 0:
            faasr_log(f"ERROR: Failed to download batch file {batch_file}")
            raise RuntimeError(f"Failed to download batch file {batch_file}")

        # Load batch data
        with open(local_batch, 'r') as f:
            batch_data = json.load(f)

        faasr_log(f"Loaded batch {batch_data['batch_id']} with {batch_data['num_frames']} frames")

        # Process each frame
        all_detections = []

        for frame_info in batch_data['frames']:
            frame_index = frame_info['frame_index']
            shape = tuple(frame_info['shape'])
            dtype = np.dtype(frame_info['dtype'])

            # Decode frame from base64
            frame_bytes = base64.b64decode(frame_info['data'])
            frame = np.frombuffer(frame_bytes, dtype=dtype).reshape(shape)

            # Convert to blob for the network
            # Faster R-CNN typically uses image size of 600x600 or original size
            # scalefactor=1.0 (no scaling), mean subtraction can vary
            blob = cv2.dnn.blobFromImage(
                frame,
                scalefactor=1.0,
                size=(frame.shape[1], frame.shape[0]),
                mean=(0, 0, 0),
                swapRB=True,
                crop=False
            )

            # Set input and run forward pass
            net.setInput(blob)
            detections = net.forward()

            # Process detections
            # Output shape: (1, 1, num_detections, 7)
            # Each detection: [batch_id, class_id, confidence, x1, y1, x2, y2]
            frame_detections = []

            for i in range(detections.shape[2]):
                confidence = float(detections[0, 0, i, 2])

                # Filter by confidence threshold > 0.5
                if confidence > 0.5:
                    class_id = int(detections[0, 0, i, 1])

                    # class_id is 1-indexed, labels list is 0-indexed
                    if 1 <= class_id <= len(labels):
                        label = labels[class_id - 1]
                    else:
                        # Unknown class, skip
                        continue

                    detection = {
                        "label": label,
                        "class": class_id,
                        "score": round(confidence, 4)
                    }
                    frame_detections.append(detection)

            all_detections.append({
                "frame_index": frame_index,
                "detections": frame_detections
            })

            faasr_log(f"Frame {frame_index}: found {len(frame_detections)} detections with confidence > 0.5")

        # Prepare output
        output_data = {
            "batch_id": batch_data['batch_id'],
            "rank": rank,
            "num_frames": len(all_detections),
            "frame_detections": all_detections
        }

        # Write output to local file
        local_output = os.path.join(tmpdir, "detections.json")
        with open(local_output, 'w') as f:
            json.dump(output_data, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Uploaded {output_file}")

    faasr_log(f"detect_objects rank {rank} completed successfully")
