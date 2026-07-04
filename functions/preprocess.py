import os
import tempfile
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import pickle


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "synthetic_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input dataset synthetic_dataset.csv must exist in S3 before preprocessing")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "train_test_data.npz" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Preprocessed training/test data train_test_data.npz must be uploaded to S3 after preprocessing")
        raise SystemExit(1)
# --- end contract helpers ---


def preprocess(folder: str, input1: str, output1: str) -> None:
    """
    Preprocess the dataset for machine learning training.

    Reads the generated dataset from upstream, applies StandardScaler() to normalize
    features, then splits the data using train_test_split with test_size=0.4 and
    random_state=123. Saves the preprocessed training and test sets (X_train, X_test,
    y_train, y_test) along with the fitted scaler for use by downstream classifier
    training functions.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("Starting dataset preprocessing")

    # Download the input dataset
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        local_input_file = f.name

    try:
        faasr_get_file(local_file=local_input_file, remote_folder=folder, remote_file=input1)
        faasr_log(f"Downloaded dataset from {folder}/{input1}")

        # Load the dataset
        df = pd.read_csv(local_input_file)
        faasr_log(f"Loaded dataset with shape {df.shape}")

        # Separate features and labels
        # The label column is named "label" based on the gen function
        X = df.drop(columns=["label"]).values
        y = df["label"].values

        faasr_log(f"Features shape: {X.shape}, Labels shape: {y.shape}")

        # Apply StandardScaler to normalize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        faasr_log("Applied StandardScaler to normalize features")

        # Split data using train_test_split with test_size=0.4 and random_state=123
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y,
            test_size=0.4,
            random_state=123
        )

        faasr_log(f"Train set: X_train={X_train.shape}, y_train={y_train.shape}")
        faasr_log(f"Test set: X_test={X_test.shape}, y_test={y_test.shape}")

        # Save the preprocessed data and scaler to an npz file
        # Serialize the scaler using pickle and store as a byte array
        scaler_bytes = pickle.dumps(scaler)

        with tempfile.NamedTemporaryFile(mode='wb', suffix='.npz', delete=False) as f:
            local_output_file = f.name

        np.savez(
            local_output_file,
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            y_test=y_test,
            scaler_bytes=np.frombuffer(scaler_bytes, dtype=np.uint8)
        )
        faasr_log(f"Saved preprocessed data to local file")

        # Upload to S3
        faasr_put_file(local_file=local_output_file, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded preprocessed data to {folder}/{output1}")

    finally:
        # Clean up local files
        if os.path.exists(local_input_file):
            os.remove(local_input_file)
        if 'local_output_file' in locals() and os.path.exists(local_output_file):
            os.remove(local_output_file)

    faasr_log("Dataset preprocessing complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---