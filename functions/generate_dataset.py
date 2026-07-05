import numpy as np
from sklearn.datasets import make_classification


def generate_dataset(folder: str, output1: str, output2: str) -> None:
    """
    Generate a classification dataset using sklearn's make_classification.

    Args:
        folder: Remote S3 folder for output files
        output1: Filename for raw feature matrix X (raw_features.npy)
        output2: Filename for raw labels y (raw_labels.npy)
    """
    faasr_log("Generating classification dataset with make_classification")

    # Generate dataset with exact parameters from specification
    X, y = make_classification(
        n_samples=500,
        n_features=1024,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123
    )

    faasr_log(f"Generated dataset with shape X={X.shape}, y={y.shape}")

    # Save features to local temp file and upload
    local_features = "temp_features.npy"
    np.save(local_features, X)
    faasr_put_file(local_file=local_features, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded features to {output1}")

    # Save labels to local temp file and upload
    local_labels = "temp_labels.npy"
    np.save(local_labels, y)
    faasr_put_file(local_file=local_labels, remote_folder=folder, remote_file=output2)
    faasr_log(f"Uploaded labels to {output2}")

    faasr_log("Dataset generation complete")
