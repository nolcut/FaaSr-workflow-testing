import tempfile
import os
import json

import numpy as np
from sklearn.svm import SVC


def train_svm(folder: str, input1: str, output1: str) -> None:
    """
    Train a Support Vector Machine classifier on preprocessed data.

    Read the preprocessed dataset (X_train, X_test, y_train, y_test) from
    the upstream preprocessing step. Initialize SVC with kernel='linear'
    and C=0.025. Fit the classifier on the training data. Compute accuracy
    on the test set using clf.score(X_test, y_test). Save the SVM accuracy
    result to an output file.

    Parameters:
        folder: S3 folder for remote storage
        input1: Input filename for preprocessed data (npz format)
        output1: Output filename for SVM accuracy result (json format)
    """
    faasr_log("Starting SVM classifier training")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download preprocessed data from S3
        local_input = os.path.join(tmpdir, "preprocessed_data.npz")
        faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

        # Load the preprocessed dataset
        data = np.load(local_input)
        X_train = data["X_train"]
        X_test = data["X_test"]
        y_train = data["y_train"]
        y_test = data["y_test"]
        faasr_log(f"Loaded preprocessed data: X_train={X_train.shape}, X_test={X_test.shape}")

        # Initialize SVC with specified parameters
        clf = SVC(kernel="linear", C=0.025)
        faasr_log("Initialized SVC with kernel='linear' and C=0.025")

        # Fit the classifier on training data
        clf.fit(X_train, y_train)
        faasr_log("SVM classifier training complete")

        # Compute accuracy on test set
        accuracy = clf.score(X_test, y_test)
        faasr_log(f"SVM test accuracy: {accuracy}")

        # Save accuracy result to JSON
        result = {"classifier": "SVM", "accuracy": accuracy}
        local_output = os.path.join(tmpdir, "svm_accuracy.json")
        with open(local_output, "w") as f:
            json.dump(result, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)

    faasr_log(f"SVM accuracy saved to {output1}")
