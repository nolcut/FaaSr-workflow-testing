import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def preprocess(folder: str, input1: str, output1: str) -> None:
    """
    Preprocess the dataset by applying StandardScaler to normalize features,
    then splitting into training and test sets.

    Parameters from user specification:
    - StandardScaler for normalization
    - train_test_split with test_size=0.4, random_state=123
    """
    faasr_log("Starting preprocessing of classification dataset")

    # Download the raw dataset from S3
    local_input = "raw_dataset_local.npz"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

    # Load the raw dataset
    data = np.load(local_input)
    X = data["X"]
    y = data["y"]

    faasr_log(f"Loaded raw dataset with X shape: {X.shape}, y shape: {y.shape}")

    # Apply StandardScaler to normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    faasr_log("Applied StandardScaler to normalize features")

    # Split into training and test sets with exact parameters from user spec
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.4, random_state=123
    )

    faasr_log(f"Split data: X_train shape: {X_train.shape}, X_test shape: {X_test.shape}")
    faasr_log(f"Split data: y_train shape: {y_train.shape}, y_test shape: {y_test.shape}")

    # Save preprocessed data to local temp file
    local_output = "preprocessed_data_local.npz"
    np.savez_compressed(
        local_output,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test
    )

    faasr_log(f"Saved preprocessed data to {local_output}")

    # Upload to S3
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)

    faasr_log(f"Uploaded preprocessed data to {folder}/{output1}")
