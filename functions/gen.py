import tempfile
import os

import numpy as np
from sklearn.datasets import make_classification


def gen(folder: str, output1: str) -> None:
    """
    Generate a synthetic classification dataset using sklearn's make_classification.

    Parameters:
        folder: S3 folder for remote storage
        output1: Output filename for the raw dataset (npz format)
    """
    faasr_log("Starting synthetic dataset generation")

    # Generate synthetic classification dataset with specified parameters
    X, y = make_classification(
        n_samples=500,
        n_features=1024,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
        n_informative=2,  # default, required since n_redundant=0
    )

    faasr_log(f"Generated dataset with shape X={X.shape}, y={y.shape}")
    faasr_log(f"Class distribution: {np.bincount(y)}")

    # Save to temporary file
    with tempfile.TemporaryDirectory() as tmpdir:
        local_file = os.path.join(tmpdir, "raw_dataset.npz")
        np.savez(local_file, X=X, y=y)

        # Upload to S3
        faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)

    faasr_log(f"Dataset saved to {output1}")
