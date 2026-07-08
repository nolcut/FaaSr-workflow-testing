import numpy as np
from sklearn.datasets import make_classification
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def gen(folder, n_samples, n_features):
    """
    Generate a synthetic classification dataset, preprocess it (train/test split
    followed by standard scaling), and persist the resulting arrays to S3 so that
    the downstream classifier functions (train_svm, train_rf) can consume them.
    """
    n_samples = int(n_samples)
    n_features = int(n_features)

    # 1. Generate the dataset
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
    )

    # 2. Split into train / test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.4, random_state=123
    )

    # 3. Standardize features (fit on train, apply to test)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # 4. Persist the preprocessed arrays to S3
    np.save("X_train.npy", X_train)
    np.save("X_test.npy", X_test)
    np.save("y_train.npy", y_train)
    np.save("y_test.npy", y_test)

    for fname in ["X_train.npy", "X_test.npy", "y_train.npy", "y_test.npy"]:
        faasr_put_file(local_file=fname, remote_folder=folder, remote_file=fname)

    faasr_log(
        f"gen: generated dataset with n_samples={n_samples}, n_features={n_features}; "
        f"train shape={X_train.shape}, test shape={X_test.shape}"
    )
