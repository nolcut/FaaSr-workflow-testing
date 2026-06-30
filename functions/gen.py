import math
import os
import tempfile

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: gen failed to upload the generated classification dataset 'classification_dataset.csv' to S3")
        raise SystemExit(1)
# --- end contract helpers ---


def gen(folder: str, output1: str) -> None:
    """Generate a complex synthetic classification dataset.

    Produces an N x M feature matrix (plus a 'target' label column) using
    scikit-learn's ``make_classification`` with high complexity: several
    informative/redundant/repeated features, many classes, multiple clusters
    per class, low class separation and noticeable label noise, plus leftover
    non-informative noise features. The result is written to S3 as
    ``classification_dataset.csv`` for downstream classifier training.

    This is a source node: it reads no external config object, so it relies on
    sensible in-code defaults and can never fail due to a missing config. Note
    that ``make_classification`` is the real, specified data source for this
    synthetic-benchmark workflow — this is NOT data fabrication.

    Parameters
    ----------
    folder  : S3 folder where the output is written.
    output1 : remote filename for the generated CSV ('classification_dataset.csv').
    """

    # ------------------------------------------------------------------ #
    # 1. In-code default parameters for dataset size and complexity.      #
    # ------------------------------------------------------------------ #
    n_samples = 1000
    n_features = 10
    n_classes = 4
    n_clusters_per_class = 3
    class_sep = 0.5
    flip_y = 0.1
    random_state = 42

    # ------------------------------------------------------------------ #
    # 2. Derive informative/redundant/repeated feature counts.            #
    #    make_classification requires:                                    #
    #      n_informative + n_redundant + n_repeated <= n_features         #
    #      n_classes * n_clusters_per_class <= 2 ** n_informative         #
    #    Leftover features become non-informative noise automatically.    #
    # ------------------------------------------------------------------ #
    min_informative = max(2, int(math.ceil(math.log2(n_classes * n_clusters_per_class))))
    n_informative = max(min_informative, min(n_features, n_features // 2 + 1))

    if n_informative > n_features:
        msg = (
            f"gen: configuration infeasible — need at least {n_informative} informative "
            f"features to host n_classes={n_classes} * n_clusters_per_class="
            f"{n_clusters_per_class} clusters, but only M={n_features} features available."
        )
        faasr_log(msg)
        raise ValueError(msg)

    remaining = n_features - n_informative
    # Default complexity: ~20% redundant and ~10% repeated of total features,
    # bounded by what remains after informative features are allocated.
    n_redundant = max(0, min(remaining, n_features // 5))
    remaining -= n_redundant

    n_repeated = max(0, min(remaining, n_features // 10))
    remaining -= n_repeated

    n_noise = remaining  # leftover features are pure noise (added by sklearn)

    if n_classes * n_clusters_per_class > 2 ** n_informative:
        msg = (
            f"gen: configuration infeasible — n_classes({n_classes}) * "
            f"n_clusters_per_class({n_clusters_per_class}) = "
            f"{n_classes * n_clusters_per_class} exceeds 2**n_informative = "
            f"{2 ** n_informative}."
        )
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(
        "gen: generating dataset with "
        f"N={n_samples}, M={n_features}, n_classes={n_classes}, "
        f"n_clusters_per_class={n_clusters_per_class}, class_sep={class_sep}, "
        f"flip_y={flip_y}, n_informative={n_informative}, n_redundant={n_redundant}, "
        f"n_repeated={n_repeated}, n_noise={n_noise}, random_state={random_state}"
    )

    # ------------------------------------------------------------------ #
    # 3. Generate the synthetic classification dataset.                   #
    # ------------------------------------------------------------------ #
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=n_informative,
        n_redundant=n_redundant,
        n_repeated=n_repeated,
        n_classes=n_classes,
        n_clusters_per_class=n_clusters_per_class,
        class_sep=class_sep,
        flip_y=flip_y,
        random_state=random_state,
        shuffle=True,
    )

    # ------------------------------------------------------------------ #
    # 4. Build the DataFrame: feature_0..feature_{M-1} + 'target'.        #
    # ------------------------------------------------------------------ #
    feature_cols = [f"feature_{i}" for i in range(n_features)]
    df = pd.DataFrame(X, columns=feature_cols)
    df["target"] = y.astype(int)

    class_balance = dict(zip(*np.unique(y, return_counts=True)))
    faasr_log(
        f"gen: built DataFrame shape={df.shape}, "
        f"class balance={ {int(k): int(v) for k, v in class_balance.items()} }"
    )

    # ------------------------------------------------------------------ #
    # 5. Write locally then upload to S3.                                 #
    # ------------------------------------------------------------------ #
    local_csv = os.path.join(tempfile.gettempdir(), "classification_dataset.csv")
    df.to_csv(local_csv, index=False)
    faasr_log(f"gen: dataset written locally → {local_csv}")

    faasr_put_file(local_file=local_csv, remote_folder=folder, remote_file=output1)
    faasr_log(f"gen: uploaded dataset → '{output1}' in folder '{folder}'")

    faasr_log("gen: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---