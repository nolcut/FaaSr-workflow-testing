import json
import numpy as np
from sklearn.svm import SVC


def train_svm(folder: str, input1: str, output1: str) -> None:
    """
    Train a Support Vector Machine classifier on preprocessed data.

    Uses SVC with kernel='linear' and C=0.025 as specified by user.
    Computes accuracy using clf.score(X_test, y_test).
    """
    faasr_log("Starting SVM training")

    # Download preprocessed data from S3
    local_input = "preprocessed_data_local.npz"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

    # Load preprocessed data
    data = np.load(local_input)
    X_train = data["X_train"]
    X_test = data["X_test"]
    y_train = data["y_train"]
    y_test = data["y_test"]

    faasr_log(f"Loaded preprocessed data: X_train shape: {X_train.shape}, X_test shape: {X_test.shape}")

    # Initialize SVC with user-specified parameters: kernel='linear', C=0.025
    clf = SVC(kernel='linear', C=0.025)

    faasr_log("Training SVM classifier with kernel='linear' and C=0.025")

    # Fit the classifier on training data
    clf.fit(X_train, y_train)

    faasr_log("SVM classifier trained successfully")

    # Compute accuracy on test set using clf.score
    accuracy = clf.score(X_test, y_test)

    faasr_log(f"SVM test accuracy: {accuracy}")

    # Save accuracy result to JSON
    result = {"accuracy": accuracy}
    local_output = "svm_accuracy_local.json"
    with open(local_output, "w") as f:
        json.dump(result, f)

    faasr_log(f"Saved accuracy result to {local_output}")

    # Upload to S3
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)

    faasr_log(f"Uploaded SVM accuracy to {folder}/{output1}")
