import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib


def train_random_forest(folder: str, input1: str, input2: str, input3: str, input4: str, output1: str, output2: str) -> None:
    """
    Train a Random Forest classifier on preprocessed training data.

    Args:
        folder: Remote S3 folder
        input1: X_train.npy - Scaled training features
        input2: X_test.npy - Scaled test features
        input3: y_train.npy - Training labels
        input4: y_test.npy - Test labels
        output1: random_forest_model.joblib - Trained model
        output2: random_forest_metrics.json - Accuracy metrics
    """
    faasr_log("Starting Random Forest training")

    # Download input files
    local_X_train = "X_train_local.npy"
    local_X_test = "X_test_local.npy"
    local_y_train = "y_train_local.npy"
    local_y_test = "y_test_local.npy"

    faasr_get_file(local_file=local_X_train, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_X_test, remote_folder=folder, remote_file=input2)
    faasr_get_file(local_file=local_y_train, remote_folder=folder, remote_file=input3)
    faasr_get_file(local_file=local_y_test, remote_folder=folder, remote_file=input4)

    faasr_log("Input files downloaded")

    # Load the data
    X_train = np.load(local_X_train)
    X_test = np.load(local_X_test)
    y_train = np.load(local_y_train)
    y_test = np.load(local_y_test)

    faasr_log(f"Training data shape: X_train={X_train.shape}, y_train={y_train.shape}")
    faasr_log(f"Test data shape: X_test={X_test.shape}, y_test={y_test.shape}")

    # Initialize RandomForestClassifier with specified parameters
    # max_depth=5, n_estimators=10, no random_state (no seeding)
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)

    # Fit the classifier on training data
    faasr_log("Fitting Random Forest classifier")
    clf.fit(X_train, y_train)

    # Calculate accuracy using clf.score on test data
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"Random Forest accuracy: {accuracy}")

    # Save the trained model
    local_model = "random_forest_model_local.joblib"
    joblib.dump(clf, local_model)
    faasr_put_file(local_file=local_model, remote_folder=folder, remote_file=output1)
    faasr_log(f"Model saved to {output1}")

    # Save accuracy metrics
    metrics = {
        "model": "RandomForest",
        "accuracy": accuracy,
        "max_depth": 5,
        "n_estimators": 10
    }
    local_metrics = "random_forest_metrics_local.json"
    with open(local_metrics, "w") as f:
        json.dump(metrics, f, indent=2)
    faasr_put_file(local_file=local_metrics, remote_folder=folder, remote_file=output2)
    faasr_log(f"Metrics saved to {output2}")

    faasr_log("Random Forest training complete")
