import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib


def train_random_forest(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Train a Random Forest classifier on preprocessed data.

    Parameters:
        folder: Remote folder for S3 storage
        input1: Filename for preprocessed data (preprocessed_data.npz)
        output1: Filename for trained model (random_forest_model.joblib)
        output2: Filename for accuracy results (random_forest_accuracy.json)
    """
    faasr_log("Starting Random Forest training")

    # Download preprocessed data from S3
    local_input = "temp_preprocessed_data.npz"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

    # Load the preprocessed data
    data = np.load(local_input)
    X_train = data["X_train"]
    X_test = data["X_test"]
    y_train = data["y_train"]
    y_test = data["y_test"]

    faasr_log(f"Loaded data: X_train shape={X_train.shape}, X_test shape={X_test.shape}")

    # Create and train Random Forest classifier
    # max_depth=5, n_estimators=10, no random_state (no seeding)
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    clf.fit(X_train, y_train)

    faasr_log("Random Forest model trained")

    # Calculate accuracy on test data using clf.score
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"Test accuracy: {accuracy}")

    # Save the trained model
    local_model = "temp_random_forest_model.joblib"
    joblib.dump(clf, local_model)
    faasr_put_file(local_file=local_model, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded trained model to {output1}")

    # Save accuracy results as JSON
    accuracy_results = {"accuracy": accuracy}
    local_accuracy = "temp_random_forest_accuracy.json"
    with open(local_accuracy, "w") as f:
        json.dump(accuracy_results, f)
    faasr_put_file(local_file=local_accuracy, remote_folder=folder, remote_file=output2)
    faasr_log(f"Uploaded accuracy results to {output2}")

    faasr_log("Random Forest training complete")
