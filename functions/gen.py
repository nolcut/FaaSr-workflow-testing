import os
import tempfile

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Generated classification dataset CSV was not found in S3 after upload")
        raise SystemExit(1)
# --- end contract helpers ---


def gen(folder: str, output1: str) -> None:
    """Generate a synthetic classification dataset and upload it to S3.

    Uses scikit-learn's make_classification to produce a realistic,
    reproducible dataset with N samples and M features plus a target column.

    Args:
        folder: Remote S3 folder (passed through to faasr_put_file).
        output1: Remote filename for the output CSV (e.g. "classification_dataset.csv").
    """
    # Dataset hyper-parameters — reproducible via fixed random_state
    N = 1000       # number of samples
    M = 20         # total number of features
    N_INFORMATIVE = 10   # features that carry actual signal
    N_REDUNDANT = 5      # linear combinations of informative features
    N_CLASSES = 2        # binary classification
    RANDOM_STATE = 42

    faasr_log(
        f"gen: Generating classification dataset — "
        f"N={N}, M={M}, n_informative={N_INFORMATIVE}, "
        f"n_redundant={N_REDUNDANT}, n_classes={N_CLASSES}, "
        f"random_state={RANDOM_STATE}"
    )

    X, y = make_classification(
        n_samples=N,
        n_features=M,
        n_informative=N_INFORMATIVE,
        n_redundant=N_REDUNDANT,
        n_repeated=0,
        n_classes=N_CLASSES,
        random_state=RANDOM_STATE,
        shuffle=True,
    )

    # Build DataFrame: feature_0 … feature_{M-1}, then target
    feature_cols = [f"feature_{i}" for i in range(M)]
    df = pd.DataFrame(X, columns=feature_cols)
    df["target"] = y

    unique_vals, counts = np.unique(y, return_counts=True)
    class_dist = dict(zip(unique_vals.tolist(), counts.tolist()))
    faasr_log(f"gen: Dataset shape={df.shape}, class distribution={class_dist}")

    # Write CSV to a temp file, then upload via FaaSr
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".csv")
    os.close(tmp_fd)
    try:
        df.to_csv(tmp_path, index=False)
        faasr_log(f"gen: Uploading '{output1}' to folder '{folder}'")
        faasr_put_file(local_file=tmp_path, remote_folder=folder, remote_file=output1)
        faasr_log("gen: Upload complete — classification_dataset.csv is ready")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---