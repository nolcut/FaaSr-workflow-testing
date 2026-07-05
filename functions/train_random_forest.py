import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier


def train_random_forest(folder: str, input1: str, input2: str, input3: str, input4: str, output1: str) -> None:
    """
    Train a Random Forest classifier on preprocessed data.

    Reads X_train, X_test, y_train, y_test from upstream preprocessing,
    trains a RandomForestClassifier with max_depth=5, n_estimators=10 (no random_state),
    and outputs the model name and accuracy to a JSON file.
    """
    faasr_log("Starting Random Forest training")

    # Load training features
    local_X_train = "X_train_local.npy"
    faasr_get_file(local_file=local_X_train, remote_folder=folder, remote_file=input1)
    X_train = np.load(local_X_train)
    faasr_log(f"Loaded X_train with shape {X_train.shape}")

    # Load test features
    local_X_test = "X_test_local.npy"
    faasr_get_file(local_file=local_X_test, remote_folder=folder, remote_file=input2)
    X_test = np.load(local_X_test)
    faasr_log(f"Loaded X_test with shape {X_test.shape}")

    # Load training labels
    local_y_train = "y_train_local.npy"
    faasr_get_file(local_file=local_y_train, remote_folder=folder, remote_file=input3)
    y_train = np.load(local_y_train)
    faasr_log(f"Loaded y_train with shape {y_train.shape}")

    # Load test labels
    local_y_test = "y_test_local.npy"
    faasr_get_file(local_file=local_y_test, remote_folder=folder, remote_file=input4)
    y_test = np.load(local_y_test)
    faasr_log(f"Loaded y_test with shape {y_test.shape}")

    # Initialize RandomForestClassifier with max_depth=5, n_estimators=10, no random_state
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    faasr_log("Initialized RandomForestClassifier with max_depth=5, n_estimators=10")

    # Fit the model on training data
    clf.fit(X_train, y_train)
    faasr_log("Fitted Random Forest model on training data")

    # Calculate accuracy on test set using clf.score
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"Random Forest test accuracy: {accuracy}")

    # Create results dictionary with model name and accuracy
    results = {
        "model": "Random Forest",
        "accuracy": accuracy
    }

    # Save results to JSON file
    local_results = "random_forest_results_local.json"
    with open(local_results, "w") as f:
        json.dump(results, f)
    faasr_put_file(local_file=local_results, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved results to {output1}")

    faasr_log("Random Forest training complete")
