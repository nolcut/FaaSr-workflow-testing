import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier


def train_random_forest(folder: str, input1: str, input2: str, input3: str, input4: str, output1: str) -> None:
    """Train a Random Forest classifier on preprocessed data.

    Loads training and test datasets from the preprocessing step, trains a
    RandomForestClassifier with max_depth=5 and n_estimators=10 (no seeding),
    and computes accuracy on the test set.
    """
    faasr_log("Starting Random Forest training")

    # Download preprocessed data from S3
    local_X_train = "X_train_local.npy"
    local_X_test = "X_test_local.npy"
    local_y_train = "y_train_local.npy"
    local_y_test = "y_test_local.npy"

    faasr_get_file(local_file=local_X_train, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_X_test, remote_folder=folder, remote_file=input2)
    faasr_get_file(local_file=local_y_train, remote_folder=folder, remote_file=input3)
    faasr_get_file(local_file=local_y_test, remote_folder=folder, remote_file=input4)

    # Load the data
    X_train = np.load(local_X_train)
    X_test = np.load(local_X_test)
    y_train = np.load(local_y_train)
    y_test = np.load(local_y_test)

    faasr_log(f"Loaded data: X_train {X_train.shape}, X_test {X_test.shape}, y_train {y_train.shape}, y_test {y_test.shape}")

    # Initialize RandomForestClassifier with max_depth=5, n_estimators=10, no seeding
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)

    # Fit the model on training data
    clf.fit(X_train, y_train)
    faasr_log("Random Forest model trained")

    # Compute accuracy on test set using clf.score()
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"Random Forest test accuracy: {accuracy}")

    # Output the accuracy result as JSON
    result = {"accuracy": accuracy}
    local_output = "rf_accuracy_local.json"
    with open(local_output, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved accuracy result to {output1}")

    faasr_log("Random Forest training complete")
