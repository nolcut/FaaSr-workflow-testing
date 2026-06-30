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
    """Generate a complex synthetic classification dataset and upload it to S3.

    Complexity is increased relative to scikit-learn defaults via:
      - More informative features (n_informative = 10)
      - Multiple clusters per class (n_clusters_per_class = 2)
      - Higher feature redundancy (n_redundant = 5)
      - Lower class separation (class_sep = 0.5)
      - Higher label noise (flip_y = 0.05)

    The resulting CSV has columns feature_0 … feature_{M-1} and target.

    Parameters
    ----------
    folder  : S3 folder where the output CSV will be written.
    output1 : Remote filename for the generated CSV (e.g. 'classification_dataset.csv').
    """

    # Configurable dataset dimensions — defaults representative of a moderately
    # large, non-trivial classification problem.
    N = 2000   # number of samples
    M = 20     # number of features (total)

    faasr_log(f"gen: generating classification dataset — N={N}, M={M}")

    # Derived complexity parameters (must satisfy scikit-learn's constraints):
    #   n_informative + n_redundant + n_repeated <= n_features
    #   n_informative >= n_classes * n_clusters_per_class  (for 2 classes: >= 2*2=4)
    n_informative = min(10, M // 2)          # at most half the features
    n_redundant = min(5, M - n_informative - 2)  # leave at least 2 "useless"
    n_redundant = max(n_redundant, 0)
    n_clusters_per_class = 2
    n_classes = 2
    class_sep = 0.5    # lower → harder separation
    flip_y = 0.05      # 5 % label noise

    faasr_log(
        f"gen: make_classification params — "
        f"n_informative={n_informative}, n_redundant={n_redundant}, "
        f"n_clusters_per_class={n_clusters_per_class}, "
        f"class_sep={class_sep}, flip_y={flip_y}"
    )

    X, y = make_classification(
        n_samples=N,
        n_features=M,
        n_informative=n_informative,
        n_redundant=n_redundant,
        n_repeated=0,
        n_classes=n_classes,
        n_clusters_per_class=n_clusters_per_class,
        class_sep=class_sep,
        flip_y=flip_y,
        random_state=42,
    )

    faasr_log(f"gen: dataset generated — shape={X.shape}, class balance={dict(zip(*np.unique(y, return_counts=True)))}")

    # Build DataFrame with named feature columns and a target column.
    feature_cols = [f"feature_{i}" for i in range(M)]
    df = pd.DataFrame(X, columns=feature_cols)
    df["target"] = y

    faasr_log(f"gen: DataFrame shape={df.shape}, columns={list(df.columns[:4])} … target")

    # Write CSV to a local temp file, then upload to S3.
    local_csv = os.path.join(tempfile.gettempdir(), "gen_classification_dataset.csv")
    df.to_csv(local_csv, index=False)
    faasr_log(f"gen: CSV written locally → {local_csv}")

    faasr_put_file(local_file=local_csv, remote_folder=folder, remote_file=output1)
    faasr_log(f"gen: uploaded '{output1}' to folder '{folder}'")

    faasr_log("gen: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---