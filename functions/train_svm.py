import json
import numpy as np
from sklearn.svm import SVC
import joblib


def train_svm(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Train an SVM classifier on preprocessed data.

    Parameters:
        folder: Remote folder for S3 storage
        input1: Filename for preprocessed data (preprocessed_data.npz)
        output1: Filename for trained model (svm_model.joblib)
        output2: Filename for accuracy results (svm_accuracy.json)
    """
    faasr_log("Starting SVM training")

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

    # Create and train SVM classifier
    # kernel='linear', C=0.025 as specified
    clf = SVC(kernel='linear', C=0.025)
    clf.fit(X_train, y_train)

    faasr_log("SVM model trained")

    # Calculate accuracy on test data using clf.score
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"Test accuracy: {accuracy}")

    # Save the trained model
    local_model = "temp_svm_model.joblib"
    joblib.dump(clf, local_model)
    faasr_put_file(local_file=local_model, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded trained model to {output1}")

    # Save accuracy results as JSON
    accuracy_results = {"accuracy": accuracy}
    local_accuracy = "temp_svm_accuracy.json"
    with open(local_accuracy, "w") as f:
        json.dump(accuracy_results, f)
    faasr_put_file(local_file=local_accuracy, remote_folder=folder, remote_file=output2)
    faasr_log(f"Uploaded accuracy results to {output2}")

    faasr_log("SVM training complete")
