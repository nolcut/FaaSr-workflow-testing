import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier


def train_random_forest(folder: str, input1: str, output1: str) -> None:
    """
    Train a Random Forest classifier on preprocessed data.

    Uses RandomForestClassifier with max_depth=5 and n_estimators=10 as specified by user.
    No random_state seeding as per user specification.
    Computes accuracy using clf.score(X_test, y_test).
    """
    faasr_log("Starting Random Forest training")

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

    # Initialize RandomForestClassifier with user-specified parameters:
    # max_depth=5, n_estimators=10, no random_state (no seeding)
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)

    faasr_log("Training Random Forest classifier with max_depth=5 and n_estimators=10")

    # Fit the classifier on training data
    clf.fit(X_train, y_train)

    faasr_log("Random Forest classifier trained successfully")

    # Compute accuracy on test set using clf.score
    accuracy = clf.score(X_test, y_test)

    faasr_log(f"Random Forest test accuracy: {accuracy}")

    # Save accuracy result to JSON
    result = {"accuracy": accuracy}
    local_output = "random_forest_accuracy_local.json"
    with open(local_output, "w") as f:
        json.dump(result, f)

    faasr_log(f"Saved accuracy result to {local_output}")

    # Upload to S3
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)

    faasr_log(f"Uploaded Random Forest accuracy to {folder}/{output1}")
