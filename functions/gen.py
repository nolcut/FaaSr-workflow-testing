import numpy as np
from sklearn.datasets import make_classification


def gen(folder: str, output1: str, output2: str) -> None:
    """Generate a synthetic classification dataset using sklearn's make_classification.

    Creates a dataset with 500 samples and 1024 features, saves raw features and labels
    as separate npy files for downstream preprocessing.
    """
    faasr_log("Generating synthetic classification dataset with make_classification")

    # Generate synthetic classification dataset with specified parameters
    X, y = make_classification(
        n_samples=500,
        n_features=1024,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123
    )

    faasr_log(f"Generated dataset: X shape={X.shape}, y shape={y.shape}")
    faasr_log(f"Class distribution: class 0={np.sum(y == 0)}, class 1={np.sum(y == 1)}")

    # Save features to local temp file and upload
    local_features = "tmp_raw_features.npy"
    np.save(local_features, X)
    faasr_put_file(local_file=local_features, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved raw features to {output1}")

    # Save labels to local temp file and upload
    local_labels = "tmp_raw_labels.npy"
    np.save(local_labels, y)
    faasr_put_file(local_file=local_labels, remote_folder=folder, remote_file=output2)
    faasr_log(f"Saved raw labels to {output2}")

    faasr_log("Dataset generation complete")
