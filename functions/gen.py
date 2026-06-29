import os
import tempfile

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: gen: output classification_dataset.csv was not found in S3 after upload")
        raise SystemExit(1)
# --- end contract helpers ---


def gen(folder: str, output1: str) -> None:
    """
    Generate a synthetic classification dataset using scikit-learn's
    make_classification utility and upload it to S3.

    Produces a CSV with columns:  feature_0, feature_1, ..., feature_N, label
    """
    faasr_log("gen: starting synthetic classification dataset generation")

    # Generate the dataset — 1000 samples, 20 features (10 informative, 5 redundant)
    X, y = make_classification(
        n_samples=1000,
        n_features=20,
        n_informative=10,
        n_redundant=5,
        n_repeated=0,
        n_classes=2,
        random_state=42,
    )

    n_features = X.shape[1]
    feature_cols = [f"feature_{i}" for i in range(n_features)]

    df = pd.DataFrame(X, columns=feature_cols)
    df["label"] = y

    faasr_log(
        f"gen: dataset has {len(df)} samples, {n_features} features, "
        f"{int(df['label'].sum())} positive labels"
    )

    # Write to a temp file then upload to S3
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False
    ) as tmp:
        local_path = tmp.name

    try:
        df.to_csv(local_path, index=False)
        faasr_log(f"gen: uploading dataset to {folder}/{output1}")
        faasr_put_file(
            local_file=local_path,
            remote_folder=folder,
            remote_file=output1,
        )
        faasr_log("gen: upload complete")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---