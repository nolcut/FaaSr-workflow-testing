"""Preprocess the synthetic dataset: standardize features and split into train/test sets."""

import os
import tempfile

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

try:
    from faasr import faasr_get_file, faasr_log, faasr_put_file
except ImportError:
    # For testing with stubs
    pass


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "synthetic_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input synthetic dataset CSV must exist in S3 before preprocessing")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "X_train.npy" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Training features array must be uploaded to S3 after preprocessing")
        raise SystemExit(1)
    if "X_test.npy" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Test features array must be uploaded to S3 after preprocessing")
        raise SystemExit(1)
    if "y_train.npy" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Training labels array must be uploaded to S3 after preprocessing")
        raise SystemExit(1)
    if "y_test.npy" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Test labels array must be uploaded to S3 after preprocessing")
        raise SystemExit(1)
# --- end contract helpers ---


def preprocess_data(folder: str, input1: str, output1: str, output2: str, output3: str, output4: str) -> None:
    """Load synthetic dataset, standardize features, and split into train/test sets.

    Standardizes all features using sklearn's StandardScaler and splits data with
    a 40% test size ratio. Saves preprocessed arrays as numpy files.

    Args:
        folder: Remote S3 folder path
        input1: Input filename for the synthetic dataset CSV
        output1: Output filename for training features (X_train.npy)
        output2: Output filename for test features (X_test.npy)
        output3: Output filename for training labels (y_train.npy)
        output4: Output filename for test labels (y_test.npy)
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("Starting data preprocessing")

    # Create temporary directory for local file operations
    with tempfile.TemporaryDirectory() as tmpdir:
        # Download the input dataset
        local_input = os.path.join(tmpdir, "synthetic_dataset.csv")
        faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)
        faasr_log(f"Downloaded {input1} from {folder}")

        # Load the dataset
        df = pd.read_csv(local_input)
        faasr_log(f"Loaded dataset with shape: {df.shape}")

        # Separate features and target
        # Features are all columns except 'target'
        feature_columns = [col for col in df.columns if col != "target"]
        X = df[feature_columns].values
        y = df["target"].values

        faasr_log(f"Features shape: {X.shape}, Target shape: {y.shape}")

        # Standardize features using StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        faasr_log("Standardized features using StandardScaler")

        # Split into training and test sets with 40% test size
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.4, random_state=42
        )

        faasr_log(f"Split data: X_train={X_train.shape}, X_test={X_test.shape}, "
                  f"y_train={y_train.shape}, y_test={y_test.shape}")

        # Save each array to a local temp file and upload
        local_X_train = os.path.join(tmpdir, "X_train.npy")
        local_X_test = os.path.join(tmpdir, "X_test.npy")
        local_y_train = os.path.join(tmpdir, "y_train.npy")
        local_y_test = os.path.join(tmpdir, "y_test.npy")

        np.save(local_X_train, X_train)
        np.save(local_X_test, X_test)
        np.save(local_y_train, y_train)
        np.save(local_y_test, y_test)

        faasr_log("Saved preprocessed arrays to local temp files")

        # Upload all output files to S3
        faasr_put_file(local_file=local_X_train, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded {output1} to {folder}")

        faasr_put_file(local_file=local_X_test, remote_folder=folder, remote_file=output2)
        faasr_log(f"Uploaded {output2} to {folder}")

        faasr_put_file(local_file=local_y_train, remote_folder=folder, remote_file=output3)
        faasr_log(f"Uploaded {output3} to {folder}")

        faasr_put_file(local_file=local_y_test, remote_folder=folder, remote_file=output4)
        faasr_log(f"Uploaded {output4} to {folder}")

    faasr_log("Data preprocessing complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---