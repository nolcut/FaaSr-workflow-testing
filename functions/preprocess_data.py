import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def preprocess_data(folder: str, input1: str, input2: str, output1: str, output2: str, output3: str, output4: str) -> None:
    """
    Preprocess the dataset by normalizing features with StandardScaler and splitting into train/test sets.

    Args:
        folder: Remote S3 folder for input/output files
        input1: Filename for raw features (raw_features.npy)
        input2: Filename for raw labels (raw_labels.npy)
        output1: Filename for training features (X_train.npy)
        output2: Filename for test features (X_test.npy)
        output3: Filename for training labels (y_train.npy)
        output4: Filename for test labels (y_test.npy)
    """
    faasr_log("Starting data preprocessing")

    # Download raw features
    local_features = "temp_raw_features.npy"
    faasr_get_file(local_file=local_features, remote_folder=folder, remote_file=input1)
    X = np.load(local_features)
    faasr_log(f"Loaded raw features with shape {X.shape}")

    # Download raw labels
    local_labels = "temp_raw_labels.npy"
    faasr_get_file(local_file=local_labels, remote_folder=folder, remote_file=input2)
    y = np.load(local_labels)
    faasr_log(f"Loaded raw labels with shape {y.shape}")

    # Apply StandardScaler to normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    faasr_log("Applied StandardScaler to normalize features")

    # Split into train and test sets with test_size=0.4, random_state=123
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y,
        test_size=0.4,
        random_state=123
    )
    faasr_log(f"Split data: X_train={X_train.shape}, X_test={X_test.shape}, y_train={y_train.shape}, y_test={y_test.shape}")

    # Save and upload X_train
    local_X_train = "temp_X_train.npy"
    np.save(local_X_train, X_train)
    faasr_put_file(local_file=local_X_train, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded {output1}")

    # Save and upload X_test
    local_X_test = "temp_X_test.npy"
    np.save(local_X_test, X_test)
    faasr_put_file(local_file=local_X_test, remote_folder=folder, remote_file=output2)
    faasr_log(f"Uploaded {output2}")

    # Save and upload y_train
    local_y_train = "temp_y_train.npy"
    np.save(local_y_train, y_train)
    faasr_put_file(local_file=local_y_train, remote_folder=folder, remote_file=output3)
    faasr_log(f"Uploaded {output3}")

    # Save and upload y_test
    local_y_test = "temp_y_test.npy"
    np.save(local_y_test, y_test)
    faasr_put_file(local_file=local_y_test, remote_folder=folder, remote_file=output4)
    faasr_log(f"Uploaded {output4}")

    faasr_log("Data preprocessing complete")
