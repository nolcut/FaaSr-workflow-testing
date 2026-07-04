import os
import tempfile
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "synthetic_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Synthetic dataset CSV was not uploaded to S3")
        raise SystemExit(1)
# --- end contract helpers ---


def gen(folder: str, output1: str) -> None:
    """
    Generate a synthetic classification dataset using sklearn's make_classification.

    Creates an imbalanced binary classification dataset with:
    - n_samples=500
    - n_features=1024
    - n_redundant=0
    - n_clusters_per_class=2
    - weights=[0.9, 0.1]
    - flip_y=0.1
    - random_state=123

    Saves features (X) and labels (y) to a CSV file.
    """
    faasr_log("Starting synthetic dataset generation")

    # Generate synthetic classification dataset with exact parameters from spec
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

    # Create DataFrame with features and label
    # Name feature columns as feature_0, feature_1, ..., feature_1023
    feature_columns = [f"feature_{i}" for i in range(X.shape[1])]
    df = pd.DataFrame(X, columns=feature_columns)
    df["label"] = y

    faasr_log(f"Dataset has {df.shape[0]} samples and {df.shape[1]} columns")
    unique_vals, counts = np.unique(y, return_counts=True)
    faasr_log(f"Class distribution: {dict(zip(unique_vals, counts))}")

    # Write to local temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        local_file = f.name
        df.to_csv(f, index=False)

    try:
        # Upload to S3
        faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded synthetic dataset to {folder}/{output1}")
    finally:
        # Clean up local file
        if os.path.exists(local_file):
            os.remove(local_file)

    faasr_log("Dataset generation complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---