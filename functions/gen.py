import numpy as np
from sklearn.datasets import make_classification


def gen(folder: str, output1: str, output2: str) -> None:
    """
    Generate a synthetic classification dataset using sklearn's make_classification.

    Parameters:
        folder: Remote folder for S3 storage
        output1: Filename for raw features (X)
        output2: Filename for raw labels (y)
    """
    faasr_log("Starting dataset generation with make_classification")

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
    faasr_log(f"Class distribution: {np.bincount(y)}")

    # Save features to local temp file and upload
    local_features = "temp_raw_features.npy"
    np.save(local_features, X)
    faasr_put_file(local_file=local_features, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded features to {output1}")

    # Save labels to local temp file and upload
    local_labels = "temp_raw_labels.npy"
    np.save(local_labels, y)
    faasr_put_file(local_file=local_labels, remote_folder=folder, remote_file=output2)
    faasr_log(f"Uploaded labels to {output2}")

    faasr_log("Dataset generation complete")
