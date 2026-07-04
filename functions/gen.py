import numpy as np
from sklearn.datasets import make_classification


def gen(folder: str, output1: str) -> None:
    """
    Generate a synthetic classification dataset using sklearn's make_classification.

    Parameters specified by user:
    - n_samples=500
    - n_features=1024
    - n_redundant=0
    - n_clusters_per_class=2
    - weights=[0.9, 0.1]
    - flip_y=0.1
    - random_state=123
    """
    faasr_log("Generating synthetic classification dataset")

    # Generate dataset with exact parameters specified in CONTEXT.md
    X, y = make_classification(
        n_samples=500,
        n_features=1024,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123
    )

    faasr_log(f"Generated dataset with X shape: {X.shape}, y shape: {y.shape}")
    faasr_log(f"Class distribution: {np.bincount(y)}")

    # Save to local temp file
    local_file = "raw_dataset.npz"
    np.savez_compressed(local_file, X=X, y=y)

    faasr_log(f"Saved raw dataset to {local_file}")

    # Upload to S3
    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)

    faasr_log(f"Uploaded dataset to {folder}/{output1}")
