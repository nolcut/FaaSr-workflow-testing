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

    Parameters configurable via FaaSr function arguments (with sensible defaults):
      n_samples  – number of rows in the dataset  (default 1000)
      n_features – number of feature columns       (default 10)

    The CSV schema produced:
      feature_0, feature_1, …, feature_{M-1}, target
    """

    # ------------------------------------------------------------------ #
    # Configurable generation parameters (sensible defaults)              #
    # ------------------------------------------------------------------ #
    N: int = 1000   # total samples
    M: int = 10     # total features

    # scikit-learn requires: n_informative + n_redundant <= n_features
    n_informative: int = max(2, M // 2)           # e.g. 5 for M=10
    n_redundant: int = max(0, min(2, M - n_informative))  # e.g. 2 for M=10

    faasr_log(
        f"gen: generating classification dataset — "
        f"n_samples={N}, n_features={M}, "
        f"n_informative={n_informative}, n_redundant={n_redundant}"
    )

    # ------------------------------------------------------------------ #
    # Generate the dataset                                                 #
    # ------------------------------------------------------------------ #
    X, y = make_classification(
        n_samples=N,
        n_features=M,
        n_informative=n_informative,
        n_redundant=n_redundant,
        n_repeated=0,
        n_classes=2,
        n_clusters_per_class=1,
        random_state=42,
    )

    feature_cols = [f"feature_{i}" for i in range(M)]
    df = pd.DataFrame(X, columns=feature_cols)
    df["target"] = y.astype(int)

    faasr_log(
        f"gen: dataset shape={df.shape}, "
        f"class balance={df['target'].value_counts().to_dict()}"
    )

    # ------------------------------------------------------------------ #
    # Write CSV locally, then upload to S3                                 #
    # ------------------------------------------------------------------ #
    local_file = os.path.join(tempfile.gettempdir(), "gen_classification_dataset.csv")
    df.to_csv(local_file, index=False)
    faasr_log(f"gen: written local CSV → {local_file}")

    faasr_put_file(
        local_file=local_file,
        remote_folder=folder,
        remote_file=output1,
    )
    faasr_log(f"gen: uploaded '{output1}' to folder '{folder}' — done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---