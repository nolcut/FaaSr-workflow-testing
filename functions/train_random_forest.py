import json
import os
import tempfile

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input classification dataset 'classification_dataset.csv' must exist in S3 before training can begin")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "random_forest_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Training metrics JSON 'random_forest_metrics.json' was not found in S3 after training completed")
        raise SystemExit(1)
    if "random_forest_model.joblib" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Serialised Random Forest model 'random_forest_model.joblib' was not found in S3 after training completed")
        raise SystemExit(1)
# --- end contract helpers ---


def train_random_forest(folder: str, input1: str, output1: str, output2: str) -> None:
    """Train a Random Forest classifier on the generated classification dataset.

    Parameters
    ----------
    folder  : S3 folder where inputs live and outputs will be written.
    input1  : remote filename of the classification CSV (produced by gen).
    output1 : remote filename for the JSON metrics file.
    output2 : remote filename for the serialised joblib model.
    """

    # ------------------------------------------------------------------ #
    # 1. Download the dataset CSV from S3                                  #
    # ------------------------------------------------------------------ #
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    local_csv = os.path.join(tempfile.gettempdir(), "train_rf_input.csv")
    faasr_log(f"train_random_forest: downloading '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_csv, remote_folder=folder, remote_file=input1)

    # ------------------------------------------------------------------ #
    # 2. Load and validate the dataset                                     #
    # ------------------------------------------------------------------ #
    faasr_log("train_random_forest: loading dataset")
    df = pd.read_csv(local_csv)

    if "target" not in df.columns:
        msg = (
            f"train_random_forest: expected column 'target' not found in CSV "
            f"(columns: {list(df.columns)})"
        )
        faasr_log(msg)
        raise ValueError(msg)

    feature_cols = [c for c in df.columns if c != "target"]
    X = df[feature_cols].values.astype(np.float64)
    y = df["target"].values

    faasr_log(
        f"train_random_forest: dataset loaded — shape={df.shape}, "
        f"features={len(feature_cols)}, "
        f"class balance={dict(zip(*np.unique(y, return_counts=True)))}"
    )

    # ------------------------------------------------------------------ #
    # 3. Train / test split                                                #
    # ------------------------------------------------------------------ #
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    faasr_log(
        f"train_random_forest: split — train={len(X_train)}, test={len(X_test)}"
    )

    # ------------------------------------------------------------------ #
    # 4. Train the Random Forest                                           #
    # ------------------------------------------------------------------ #
    faasr_log("train_random_forest: fitting RandomForestClassifier(n_estimators=100)")
    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)

    # ------------------------------------------------------------------ #
    # 5. Evaluate                                                          #
    # ------------------------------------------------------------------ #
    y_pred = clf.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))
    report = classification_report(y_test, y_pred, output_dict=True)

    faasr_log(f"train_random_forest: accuracy={acc:.4f}")

    # ------------------------------------------------------------------ #
    # 6. Save metrics JSON                                                 #
    # ------------------------------------------------------------------ #
    metrics = {
        "accuracy": acc,
        "classification_report": report,
    }
    local_metrics = os.path.join(tempfile.gettempdir(), "train_rf_metrics.json")
    with open(local_metrics, "w") as fh:
        json.dump(metrics, fh, indent=2)
    faasr_log(f"train_random_forest: metrics written locally → {local_metrics}")

    # ------------------------------------------------------------------ #
    # 7. Save model with joblib                                            #
    # ------------------------------------------------------------------ #
    local_model = os.path.join(tempfile.gettempdir(), "train_rf_model.joblib")
    joblib.dump(clf, local_model)
    faasr_log(f"train_random_forest: model serialised → {local_model}")

    # ------------------------------------------------------------------ #
    # 8. Upload both artefacts to S3                                       #
    # ------------------------------------------------------------------ #
    faasr_put_file(local_file=local_metrics, remote_folder=folder, remote_file=output1)
    faasr_log(f"train_random_forest: uploaded metrics → '{output1}' in folder '{folder}'")

    faasr_put_file(local_file=local_model, remote_folder=folder, remote_file=output2)
    faasr_log(f"train_random_forest: uploaded model → '{output2}' in folder '{folder}'")

    faasr_log("train_random_forest: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---