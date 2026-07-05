import json
import numpy as np
from sklearn.svm import SVC


def train_svm(folder: str, input1: str, input2: str, input3: str, input4: str, output1: str) -> None:
    """
    Train an SVM classifier on preprocessed data.

    Reads preprocessed training/test datasets, trains SVM with kernel='linear' and C=0.025,
    and outputs model name and accuracy to JSON.
    """
    # Download input files from S3
    local_X_train = "X_train_local.npy"
    local_X_test = "X_test_local.npy"
    local_y_train = "y_train_local.npy"
    local_y_test = "y_test_local.npy"

    faasr_log("Downloading preprocessed datasets...")
    faasr_get_file(local_file=local_X_train, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_X_test, remote_folder=folder, remote_file=input2)
    faasr_get_file(local_file=local_y_train, remote_folder=folder, remote_file=input3)
    faasr_get_file(local_file=local_y_test, remote_folder=folder, remote_file=input4)

    # Load the data
    faasr_log("Loading data from local files...")
    X_train = np.load(local_X_train)
    X_test = np.load(local_X_test)
    y_train = np.load(local_y_train)
    y_test = np.load(local_y_test)

    faasr_log(f"Training data shape: X_train={X_train.shape}, y_train={y_train.shape}")
    faasr_log(f"Test data shape: X_test={X_test.shape}, y_test={y_test.shape}")

    # Initialize and train SVM classifier with specified parameters
    faasr_log("Training SVM classifier with kernel='linear', C=0.025...")
    clf = SVC(kernel='linear', C=0.025)
    clf.fit(X_train, y_train)

    # Calculate accuracy using clf.score
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"SVM accuracy: {accuracy}")

    # Prepare output
    results = {
        "model": "SVM",
        "accuracy": accuracy
    }

    # Write results to local JSON file
    local_output = "svm_results_local.json"
    with open(local_output, 'w') as f:
        json.dump(results, f, indent=2)

    # Upload to S3
    faasr_log(f"Uploading results to {output1}...")
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)

    faasr_log("train_svm completed successfully")
