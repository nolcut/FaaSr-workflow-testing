import numpy as np
from sklearn.datasets import make_classification
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def gen(N=500, M=1024, folder="ml"):
    """Generate a classification dataset, preprocess it, and persist the
    train/test splits to S3 for the downstream classifier training steps."""

    N = int(N)
    M = int(M)

    faasr_log(f"gen: generating dataset with n_samples={N}, n_features={M}")

    # Generate the dataset
    X, y = make_classification(
        n_samples=N,
        n_features=M,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
    )

    # Split into train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.4, random_state=123
    )

    # Standardize features (fit on train, apply to both)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # Save splits locally as a single compressed archive
    local_file = "dataset.npz"
    np.savez(
        local_file,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
    )

    # Persist to S3 so the parallel classifier steps can read it
    faasr_put_file(
        local_file=local_file,
        remote_folder=folder,
        remote_file="dataset.npz",
    )

    faasr_log(
        f"gen: wrote dataset.npz to {folder} "
        f"(train={X_train.shape}, test={X_test.shape})"
    )
