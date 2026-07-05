import json
import numpy as np
from sklearn.svm import SVC


def train_svm(folder: str, input1: str, input2: str, input3: str, input4: str, output1: str) -> None:
    """Train a Support Vector Machine classifier on preprocessed data.

    Load the preprocessed training and test data (X_train, X_test, y_train, y_test)
    from the upstream preprocessing step. Initialize SVC with kernel='linear' and C=0.025.
    Fit the classifier on the training data. Compute accuracy using clf.score() on the test data.
    Save the accuracy result to an output file.
    """
    faasr_log("Starting SVM training")

    # Download preprocessed training features
    local_X_train = "tmp_X_train.npy"
    faasr_get_file(local_file=local_X_train, remote_folder=folder, remote_file=input1)
    X_train = np.load(local_X_train)
    faasr_log(f"Loaded training features: shape={X_train.shape}")

    # Download preprocessed test features
    local_X_test = "tmp_X_test.npy"
    faasr_get_file(local_file=local_X_test, remote_folder=folder, remote_file=input2)
    X_test = np.load(local_X_test)
    faasr_log(f"Loaded test features: shape={X_test.shape}")

    # Download training labels
    local_y_train = "tmp_y_train.npy"
    faasr_get_file(local_file=local_y_train, remote_folder=folder, remote_file=input3)
    y_train = np.load(local_y_train)
    faasr_log(f"Loaded training labels: shape={y_train.shape}")

    # Download test labels
    local_y_test = "tmp_y_test.npy"
    faasr_get_file(local_file=local_y_test, remote_folder=folder, remote_file=input4)
    y_test = np.load(local_y_test)
    faasr_log(f"Loaded test labels: shape={y_test.shape}")

    # Initialize SVC with kernel='linear' and C=0.025
    clf = SVC(kernel='linear', C=0.025)
    faasr_log("Initialized SVC with kernel='linear' and C=0.025")

    # Fit the classifier on the training data
    clf.fit(X_train, y_train)
    faasr_log("SVM classifier fitted on training data")

    # Compute accuracy using clf.score() on the test data
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"SVM test accuracy: {accuracy}")

    # Save accuracy result to output file
    result = {
        "classifier": "SVM",
        "kernel": "linear",
        "C": 0.025,
        "accuracy": accuracy
    }
    local_output = "tmp_svm_accuracy.json"
    with open(local_output, "w") as f:
        json.dump(result, f, indent=2)

    # Upload the accuracy result
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved SVM accuracy result to {output1}")

    faasr_log("SVM training complete")
