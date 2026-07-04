import tempfile
import os

import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def preprocess(folder: str, input1: str, output1: str) -> None:
    """
    Preprocess the dataset for machine learning training.

    Read the generated dataset from upstream gen function, apply StandardScaler
    to normalize/standardize features, and split into training and testing sets.

    Parameters:
        folder: S3 folder for remote storage
        input1: Input filename for raw dataset (npz format with X, y arrays)
        output1: Output filename for preprocessed data (npz format)
    """
    faasr_log("Starting dataset preprocessing")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download raw dataset from S3
        local_input = os.path.join(tmpdir, "raw_dataset.npz")
        faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

        # Load the raw dataset
        data = np.load(local_input)
        X = data["X"]
        y = data["y"]
        faasr_log(f"Loaded dataset with shape X={X.shape}, y={y.shape}")

        # Apply StandardScaler to normalize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        faasr_log("Applied StandardScaler normalization")

        # Split into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.4, random_state=123
        )
        faasr_log(
            f"Split data: X_train={X_train.shape}, X_test={X_test.shape}, "
            f"y_train={y_train.shape}, y_test={y_test.shape}"
        )

        # Save preprocessed data to local file
        local_output = os.path.join(tmpdir, "preprocessed_data.npz")
        np.savez(
            local_output, X_train=X_train, X_test=X_test, y_train=y_train, y_test=y_test
        )

        # Upload to S3
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)

    faasr_log(f"Preprocessed data saved to {output1}")
