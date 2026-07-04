import os
import json
import tempfile
import numpy as np
from sklearn.ensemble import RandomForestClassifier


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "train_test_data.npz" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Preprocessed training/test data file must exist in S3 before training Random Forest classifier")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "random_forest_results.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Random Forest results JSON file must be uploaded to S3 after training completes")
        raise SystemExit(1)
# --- end contract helpers ---


def train_random_forest(folder: str, input1: str, output1: str) -> None:
    """
    Train a Random Forest classifier on preprocessed data.

    Loads training and test data from the npz file produced by preprocess,
    trains a Random Forest with max_depth=5 and n_estimators=10 (no random_state
    for non-deterministic training), then computes accuracy using clf.score()
    on the test set. Saves results including accuracy and model parameters to JSON.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("Starting Random Forest classifier training")

    # Download the preprocessed data
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.npz', delete=False) as f:
        local_input_file = f.name

    try:
        faasr_get_file(local_file=local_input_file, remote_folder=folder, remote_file=input1)
        faasr_log(f"Downloaded preprocessed data from {folder}/{input1}")

        # Load the preprocessed data
        data = np.load(local_input_file, allow_pickle=True)
        X_train = data['X_train']
        X_test = data['X_test']
        y_train = data['y_train']
        y_test = data['y_test']

        faasr_log(f"Loaded training data: X_train={X_train.shape}, y_train={y_train.shape}")
        faasr_log(f"Loaded test data: X_test={X_test.shape}, y_test={y_test.shape}")

        # Train Random Forest classifier with specified parameters
        # max_depth=5, n_estimators=10, no random_state (non-deterministic)
        clf = RandomForestClassifier(
            max_depth=5,
            n_estimators=10
        )

        faasr_log("Training Random Forest classifier with max_depth=5, n_estimators=10")
        clf.fit(X_train, y_train)
        faasr_log("Training complete")

        # Compute accuracy using clf.score() on test set
        accuracy = clf.score(X_test, y_test)
        faasr_log(f"Test accuracy: {accuracy:.4f}")

        # Prepare results
        results = {
            "model": "RandomForest",
            "parameters": {
                "max_depth": 5,
                "n_estimators": 10,
                "random_state": None
            },
            "accuracy": accuracy,
            "train_samples": int(X_train.shape[0]),
            "test_samples": int(X_test.shape[0]),
            "n_features": int(X_train.shape[1])
        }

        # Write results to local JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            local_output_file = f.name
            json.dump(results, f, indent=2)

        # Upload to S3
        faasr_put_file(local_file=local_output_file, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded results to {folder}/{output1}")

    finally:
        # Clean up local files
        if os.path.exists(local_input_file):
            os.remove(local_input_file)
        if 'local_output_file' in locals() and os.path.exists(local_output_file):
            os.remove(local_output_file)

    faasr_log("Random Forest training complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---