import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier


def train_random_forest(folder: str, input1: str, input2: str, input3: str, input4: str, output1: str) -> None:
    """Train a Random Forest classifier on preprocessed data.

    Load the preprocessed training and test data (X_train, X_test, y_train, y_test)
    from the upstream preprocessing step. Initialize RandomForestClassifier with
    max_depth=5 and n_estimators=10, without setting random_state or any other seeding.
    Fit the classifier on the training data. Compute accuracy using clf.score() on the test data.
    Save the accuracy result to an output file.
    """
    faasr_log("Starting Random Forest training")

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

    # Initialize RandomForestClassifier with max_depth=5 and n_estimators=10
    # Do not set random_state or any other seeding as per the spec
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    faasr_log("Initialized RandomForestClassifier with max_depth=5 and n_estimators=10")

    # Fit the classifier on the training data
    clf.fit(X_train, y_train)
    faasr_log("Random Forest classifier fitted on training data")

    # Compute accuracy using clf.score() on the test data
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"Random Forest test accuracy: {accuracy}")

    # Save accuracy result to output file
    result = {
        "classifier": "RandomForest",
        "max_depth": 5,
        "n_estimators": 10,
        "accuracy": accuracy
    }
    local_output = "tmp_random_forest_accuracy.json"
    with open(local_output, "w") as f:
        json.dump(result, f, indent=2)

    # Upload the accuracy result
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved Random Forest accuracy result to {output1}")

    faasr_log("Random Forest training complete")
