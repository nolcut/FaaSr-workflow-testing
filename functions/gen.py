import os
import tempfile

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Generated classification dataset CSV was not uploaded to S3")
        raise SystemExit(1)
# --- end contract helpers ---


def gen(folder: str, output1: str) -> None:
    """Generate a synthetic classification dataset and upload it to S3.

    Uses scikit-learn's make_classification to create a dataset with N samples
    and M features, then saves it as a CSV with feature columns and a target
    label column.
    """
    N = 1000  # number of samples
    M = 10    # number of features

    faasr_log(f"Generating synthetic classification dataset: N={N} samples, M={M} features")

    X, y = make_classification(
        n_samples=N,
        n_features=M,
        n_informative=5,
        n_redundant=2,
        n_repeated=0,
        n_classes=2,
        random_state=42,
    )

    feature_cols = [f"feature_{i}" for i in range(M)]
    df = pd.DataFrame(X, columns=feature_cols)
    df["target"] = y

    faasr_log(f"Dataset shape: {df.shape[0]} rows x {df.shape[1]} columns")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        local_path = tmp.name

    try:
        df.to_csv(local_path, index=False)
        faasr_log(f"Uploading dataset to {folder}/{output1}")
        faasr_put_file(local_file=local_path, remote_folder=folder, remote_file=output1)
        faasr_log("Dataset upload complete")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---