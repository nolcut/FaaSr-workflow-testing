import numpy as np
from sklearn.datasets import make_classification
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def gen(N=500, M=1024):
    """Generate a synthetic classification dataset, preprocess it (StandardScaler +
    train_test_split), and persist the train/test splits to S3 for the downstream
    classifier functions.
    """
    N = int(N)
    M = int(M)

    faasr_log(f"gen: generating dataset with N={N} samples and M={M} features")

    # 1) Dataset generation
    X, y = make_classification(
        n_samples=N,
        n_features=M,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
    )

    # 2) Preprocessing: StandardScaler + train_test_split
    X_scaled = StandardScaler().fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.4, random_state=123
    )

    faasr_log(
        f"gen: train shape={X_train.shape}, test shape={X_test.shape}"
    )

    # 3) Persist splits to S3 as a single compressed npz artifact
    local_file = "dataset.npz"
    np.savez(
        local_file,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
    )

    faasr_put_file(
        local_file=local_file,
        remote_folder="ml-pipeline",
        remote_file="dataset.npz",
    )

    faasr_log("gen: dataset.npz uploaded to ml-pipeline/dataset.npz")
