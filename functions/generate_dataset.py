import numpy as np
from sklearn.datasets import make_classification


def generate_dataset(folder: str, output1: str, output2: str) -> None:
    """
    Generate a synthetic classification dataset using sklearn's make_classification
    with the specified parameters and save to output files.
    """
    faasr_log("Generating synthetic classification dataset")

    # Generate dataset with specified parameters
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

    # Save features (X) to local file
    local_features = "raw_features.npy"
    np.save(local_features, X)
    faasr_put_file(local_file=local_features, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved features to {output1}")

    # Save labels (y) to local file
    local_labels = "raw_labels.npy"
    np.save(local_labels, y)
    faasr_put_file(local_file=local_labels, remote_folder=folder, remote_file=output2)
    faasr_log(f"Saved labels to {output2}")

    faasr_log("Dataset generation complete")
