import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def preprocess(folder: str, input1: str, input2: str, output1: str, output2: str, output3: str, output4: str) -> None:
    """Preprocess the dataset: normalize features and split into train/test sets.

    Loads raw features and labels from upstream gen function, applies StandardScaler
    to normalize features, and splits into training/testing sets using train_test_split
    with test_size=0.4 and random_state=123.
    """
    faasr_log("Starting preprocessing of classification dataset")

    # Download raw features and labels from S3
    local_features = "raw_features_local.npy"
    local_labels = "raw_labels_local.npy"

    faasr_get_file(local_file=local_features, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_labels, remote_folder=folder, remote_file=input2)

    # Load the data
    X = np.load(local_features)
    y = np.load(local_labels)

    faasr_log(f"Loaded raw data with shape X: {X.shape}, y: {y.shape}")

    # Apply StandardScaler to normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    faasr_log("Applied StandardScaler normalization to features")

    # Split data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y,
        test_size=0.4,
        random_state=123
    )

    faasr_log(f"Split data: X_train {X_train.shape}, X_test {X_test.shape}, y_train {y_train.shape}, y_test {y_test.shape}")

    # Save preprocessed data to local files and upload to S3
    local_X_train = "X_train_local.npy"
    local_X_test = "X_test_local.npy"
    local_y_train = "y_train_local.npy"
    local_y_test = "y_test_local.npy"

    np.save(local_X_train, X_train)
    faasr_put_file(local_file=local_X_train, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved X_train to {output1}")

    np.save(local_X_test, X_test)
    faasr_put_file(local_file=local_X_test, remote_folder=folder, remote_file=output2)
    faasr_log(f"Saved X_test to {output2}")

    np.save(local_y_train, y_train)
    faasr_put_file(local_file=local_y_train, remote_folder=folder, remote_file=output3)
    faasr_log(f"Saved y_train to {output3}")

    np.save(local_y_test, y_test)
    faasr_put_file(local_file=local_y_test, remote_folder=folder, remote_file=output4)
    faasr_log(f"Saved y_test to {output4}")

    faasr_log("Preprocessing complete")
