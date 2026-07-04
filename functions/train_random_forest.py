import json
import tempfile
import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier


def train_random_forest(folder: str, input1: str, output1: str) -> None:
    """Train a Random Forest classifier on preprocessed data and save accuracy."""

    faasr_log("Starting Random Forest training")

    # Download preprocessed data
    with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as tmp_input:
        local_input = tmp_input.name

    try:
        faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)
        faasr_log(f"Downloaded preprocessed data: {input1}")

        # Load the preprocessed dataset
        data = np.load(local_input)
        X_train = data["X_train"]
        X_test = data["X_test"]
        y_train = data["y_train"]
        y_test = data["y_test"]
        faasr_log(f"Loaded data: X_train shape={X_train.shape}, X_test shape={X_test.shape}")

        # Initialize RandomForestClassifier with max_depth=5, n_estimators=10, no random_state
        clf = RandomForestClassifier(max_depth=5, n_estimators=10)
        faasr_log("Training Random Forest classifier (max_depth=5, n_estimators=10)")

        # Fit the classifier on training data
        clf.fit(X_train, y_train)
        faasr_log("Training complete")

        # Compute accuracy on test set using clf.score
        accuracy = clf.score(X_test, y_test)
        faasr_log(f"Random Forest accuracy: {accuracy}")

        # Save accuracy result to output file
        result = {"accuracy": accuracy}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_output:
            local_output = tmp_output.name
            json.dump(result, tmp_output)

        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded accuracy result: {output1}")

    finally:
        # Cleanup temp files
        if os.path.exists(local_input):
            os.remove(local_input)
        if 'local_output' in locals() and os.path.exists(local_output):
            os.remove(local_output)

    faasr_log("Random Forest training complete")
