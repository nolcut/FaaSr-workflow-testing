"""
FaaSr function: train_classifier
Train a machine learning classifier based on rank and evaluate on test data.
Rank 1: SVM with linear kernel
Rank 2: Random Forest
"""

import json
import os
import tempfile

import numpy as np
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "X_train.npy" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Training features file X_train.npy must exist in S3")
        raise SystemExit(1)
    if "X_test.npy" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Test features file X_test.npy must exist in S3")
        raise SystemExit(1)
    if "y_train.npy" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Training labels file y_train.npy must exist in S3")
        raise SystemExit(1)
    if "y_test.npy" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Test labels file y_test.npy must exist in S3")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "classifier_results_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Classifier results file must be uploaded to S3 after training")
        raise SystemExit(1)
# --- end contract helpers ---


def train_classifier(folder: str, input1: str, input2: str, input3: str, input4: str, output1: str) -> None:
    """
    Train a classifier based on rank and evaluate on test data.

    Args:
        folder: Remote folder for S3 operations
        input1: Training features filename (X_train.npy)
        input2: Test features filename (X_test.npy)
        input3: Training labels filename (y_train.npy)
        input4: Test labels filename (y_test.npy)
        output1: Output results filename with {rank} placeholder
    """
    # Get rank information
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    r = faasr_rank()
    rank = r['rank']
    max_rank = r['max_rank']

    faasr_log(f"train_classifier starting: rank {rank} of {max_rank}")

    # Resolve output filename with rank
    output_file = output1.format(rank=rank)

    # Create temporary directory for local file operations
    with tempfile.TemporaryDirectory() as tmpdir:
        # Define local file paths
        local_X_train = os.path.join(tmpdir, "X_train.npy")
        local_X_test = os.path.join(tmpdir, "X_test.npy")
        local_y_train = os.path.join(tmpdir, "y_train.npy")
        local_y_test = os.path.join(tmpdir, "y_test.npy")
        local_output = os.path.join(tmpdir, "results.json")

        # Download input files from S3
        faasr_log(f"Downloading training and test data...")
        faasr_get_file(local_file=local_X_train, remote_folder=folder, remote_file=input1)
        faasr_get_file(local_file=local_X_test, remote_folder=folder, remote_file=input2)
        faasr_get_file(local_file=local_y_train, remote_folder=folder, remote_file=input3)
        faasr_get_file(local_file=local_y_test, remote_folder=folder, remote_file=input4)

        # Load the numpy arrays
        faasr_log("Loading data arrays...")
        X_train = np.load(local_X_train)
        X_test = np.load(local_X_test)
        y_train = np.load(local_y_train)
        y_test = np.load(local_y_test)

        faasr_log(f"Data shapes - X_train: {X_train.shape}, X_test: {X_test.shape}, y_train: {y_train.shape}, y_test: {y_test.shape}")

        # Select and train classifier based on rank
        if rank == 1:
            model_type = "SVM_linear"
            faasr_log("Training SVM with linear kernel...")
            model = SVC(kernel='linear', random_state=42)
        elif rank == 2:
            model_type = "RandomForest"
            faasr_log("Training Random Forest classifier...")
            model = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            error_msg = f"Unexpected rank value: {rank}. Expected 1 or 2."
            faasr_log(f"ERROR: {error_msg}")
            raise ValueError(error_msg)

        # Train the model
        model.fit(X_train, y_train)
        faasr_log(f"{model_type} training complete.")

        # Make predictions on test data
        faasr_log("Making predictions on test data...")
        y_pred = model.predict(X_test)

        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)

        faasr_log(f"{model_type} accuracy: {accuracy:.4f}")

        # Prepare results dictionary
        results = {
            "model_type": model_type,
            "rank": rank,
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "train_samples": int(X_train.shape[0]),
            "test_samples": int(X_test.shape[0]),
            "num_features": int(X_train.shape[1])
        }

        # Save results to local JSON file
        faasr_log(f"Saving results to {output_file}...")
        with open(local_output, 'w') as f:
            json.dump(results, f, indent=2)

        # Upload results to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)

        faasr_log(f"train_classifier rank {rank} complete. Results saved to {output_file}")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---