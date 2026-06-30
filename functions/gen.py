import json
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


def gen(folder: str, input1: str, output1: str) -> None:
    """Generate a complex synthetic classification dataset.

    Produces an N x M feature matrix (plus a 'target' label column) using
    scikit-learn's ``make_classification`` with high complexity: several
    informative/redundant/repeated features, many classes, multiple clusters
    per class, low class separation and noticeable label noise, plus leftover
    non-informative noise features. The result is written to S3 as
    ``classification_dataset.csv`` for downstream classifier training.

    Parameters
    ----------
    folder  : S3 folder where the optional config lives and the output is written.
    input1  : remote filename of the optional JSON config ('gen_config.json').
    output1 : remote filename for the generated CSV ('classification_dataset.csv').
    """

    # ------------------------------------------------------------------ #
    # 1. Load the OPTIONAL configuration from S3.                          #
    #    Per the workflow spec this is a source node: the config is        #
    #    optional and sensible defaults are used when it is absent/empty.  #
    #    NOTE: this is NOT data fabrication — make_classification is the    #
    #    real, specified data source for this synthetic-benchmark task.    #
    # ------------------------------------------------------------------ #
    config = {}
    local_cfg = os.path.join(tempfile.gettempdir(), "gen_config.json")
    try:
        faasr_log(f"gen: attempting to download optional config '{input1}' from folder '{folder}'")
        faasr_get_file(local_file=local_cfg, remote_folder=folder, remote_file=input1)
        if os.path.exists(local_cfg) and os.path.getsize(local_cfg) > 0:
            with open(local_cfg, "r") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                config = loaded
                faasr_log(f"gen: loaded config keys={list(config.keys())}")
            else:
                faasr_log("gen: config JSON is not an object; using defaults")
        else:
            faasr_log("gen: no config content found; using defaults")
    except FileNotFoundError:
        faasr_log("gen: optional config not present; using defaults")
    except json.JSONDecodeError as exc:
        # The config is optional; an unpar. able file should not silently
        # corrupt the run, but we surface it loudly rather than guessing.
        faasr_log(f"gen: optional config could not be parsed as JSON: {exc}; using defaults")

    # ------------------------------------------------------------------ #
    # 2. Resolve parameters (config overrides, otherwise defaults).       #
    # ------------------------------------------------------------------ #
    def _get(key, default):
        val = config.get(key, default)
        return default if val is None else val

    n_samples = int(_get("N", 1000))
    n_features = int(_get("M", 10))
    n_classes = int(_get("n_classes", 4))
    n_clusters_per_class = int(_get("n_clusters_per_class", 3))
    class_sep = float(_get("class_sep", 0.5))
    flip_y = float(_get("flip_y", 0.1))
    random_state = int(_get("random_state", 42))

    if n_samples <= 0:
        msg = f"gen: invalid N={n_samples}; must be a positive integer"
        faasr_log(msg)
        raise ValueError(msg)
    if n_features <= 0:
        msg = f"gen: invalid M={n_features}; must be a positive integer"
        faasr_log(msg)
        raise ValueError(msg)
    if n_classes < 2:
        msg = f"gen: invalid n_classes={n_classes}; must be >= 2"
        faasr_log(msg)
        raise ValueError(msg)
    if n_clusters_per_class < 1:
        msg = f"gen: invalid n_clusters_per_class={n_clusters_per_class}; must be >= 1"
        faasr_log(msg)
        raise ValueError(msg)

    # ------------------------------------------------------------------ #
    # 3. Derive informative/redundant/repeated feature counts.            #
    #    make_classification requires:                                    #
    #      n_informative + n_redundant + n_repeated <= n_features         #
    #      n_classes * n_clusters_per_class <= 2 ** n_informative         #
    #    Leftover features become non-informative noise automatically.    #
    # ------------------------------------------------------------------ #
    # Minimum informative features needed to host all class clusters.
    min_informative = max(2, int(math.ceil(math.log2(n_classes * n_clusters_per_class))))

    n_informative = int(_get("n_informative", max(min_informative, min(n_features, n_features // 2 + 1))))
    n_informative = max(n_informative, min_informative)

    if n_informative > n_features:
        msg = (
            f"gen: configuration infeasible — need at least {n_informative} informative "
            f"features to host n_classes={n_classes} * n_clusters_per_class="
            f"{n_clusters_per_class} clusters, but only M={n_features} features requested. "
            f"Increase M or reduce n_classes/n_clusters_per_class."
        )
        faasr_log(msg)
        raise ValueError(msg)

    remaining = n_features - n_informative
    # Default complexity: ~20% redundant and ~10% repeated of total features,
    # bounded by what remains after informative features are allocated.
    n_redundant = int(_get("n_redundant", min(remaining, max(0, n_features // 5))))
    n_redundant = max(0, min(n_redundant, remaining))
    remaining -= n_redundant

    n_repeated = int(_get("n_repeated", min(remaining, max(0, n_features // 10))))
    n_repeated = max(0, min(n_repeated, remaining))
    remaining -= n_repeated

    n_noise = remaining  # leftover features are pure noise (added by sklearn)

    # Final feasibility check for the cluster constraint.
    if n_classes * n_clusters_per_class > 2 ** n_informative:
        msg = (
            f"gen: configuration infeasible — n_classes({n_classes}) * "
            f"n_clusters_per_class({n_clusters_per_class}) = "
            f"{n_classes * n_clusters_per_class} exceeds 2**n_informative = "
            f"{2 ** n_informative}. Increase M/n_informative or reduce classes/clusters."
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
    # 4. Generate the synthetic classification dataset.                   #
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
    # 5. Build the DataFrame: feature_0..feature_{M-1} + 'target'.        #
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
    # 6. Write locally then upload to S3.                                 #
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