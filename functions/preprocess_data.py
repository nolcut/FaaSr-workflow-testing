import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def preprocess_data(folder: str, input1: str, input2: str, output1: str, output2: str, output3: str, output4: str) -> None:
    """
    Preprocess the dataset: load raw features and labels, apply StandardScaler
    to standardize features, split into train/test sets, and save outputs.
    """
    faasr_log("Starting data preprocessing")

    # Load raw features (X) from upstream generate_dataset
    local_features = "raw_features_local.npy"
    faasr_get_file(local_file=local_features, remote_folder=folder, remote_file=input1)
    X = np.load(local_features)
    faasr_log(f"Loaded features with shape {X.shape}")

    # Load raw labels (y) from upstream generate_dataset
    local_labels = "raw_labels_local.npy"
    faasr_get_file(local_file=local_labels, remote_folder=folder, remote_file=input2)
    y = np.load(local_labels)
    faasr_log(f"Loaded labels with shape {y.shape}")

    # Apply StandardScaler to standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    faasr_log("Applied StandardScaler to features")

    # Split into training and test sets with test_size=0.4 and random_state=123
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.4, random_state=123
    )
    faasr_log(f"Split data: X_train={X_train.shape}, X_test={X_test.shape}, y_train={y_train.shape}, y_test={y_test.shape}")

    # Save preprocessed training features
    local_X_train = "X_train_local.npy"
    np.save(local_X_train, X_train)
    faasr_put_file(local_file=local_X_train, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved {output1}")

    # Save preprocessed test features
    local_X_test = "X_test_local.npy"
    np.save(local_X_test, X_test)
    faasr_put_file(local_file=local_X_test, remote_folder=folder, remote_file=output2)
    faasr_log(f"Saved {output2}")

    # Save training labels
    local_y_train = "y_train_local.npy"
    np.save(local_y_train, y_train)
    faasr_put_file(local_file=local_y_train, remote_folder=folder, remote_file=output3)
    faasr_log(f"Saved {output3}")

    # Save test labels
    local_y_test = "y_test_local.npy"
    np.save(local_y_test, y_test)
    faasr_put_file(local_file=local_y_test, remote_folder=folder, remote_file=output4)
    faasr_log(f"Saved {output4}")

    faasr_log("Data preprocessing complete")
