import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def preprocess(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Preprocess the dataset by applying StandardScaler for feature normalization
    and splitting into training and test sets.

    Parameters:
        folder: Remote folder for S3 storage
        input1: Filename for raw features (raw_features.npy)
        input2: Filename for raw labels (raw_labels.npy)
        output1: Filename for preprocessed data (preprocessed_data.npz)
    """
    faasr_log("Starting data preprocessing")

    # Download raw features and labels from S3
    local_features = "temp_features.npy"
    local_labels = "temp_labels.npy"

    faasr_get_file(local_file=local_features, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_labels, remote_folder=folder, remote_file=input2)

    # Load the data
    X = np.load(local_features)
    y = np.load(local_labels)

    faasr_log(f"Loaded data: X shape={X.shape}, y shape={y.shape}")

    # Apply StandardScaler for feature normalization
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    faasr_log("Applied StandardScaler normalization")

    # Split into training and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y,
        test_size=0.4,
        random_state=123
    )

    faasr_log(f"Split data: X_train shape={X_train.shape}, X_test shape={X_test.shape}")
    faasr_log(f"Training set class distribution: {np.bincount(y_train)}")
    faasr_log(f"Test set class distribution: {np.bincount(y_test)}")

    # Save preprocessed data to local npz file
    local_output = "temp_preprocessed_data.npz"
    np.savez(local_output, X_train=X_train, X_test=X_test, y_train=y_train, y_test=y_test)

    # Upload to S3
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded preprocessed data to {output1}")

    faasr_log("Preprocessing complete")
