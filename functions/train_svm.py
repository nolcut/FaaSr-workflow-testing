import json
import os
import tempfile

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input dataset classification_dataset.csv must exist in S3 before SVM training can begin")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "svm_results.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: SVM training results svm_results.json must be present in S3 after training and evaluation complete")
        raise SystemExit(1)
# --- end contract helpers ---


def train_svm(folder: str, input1: str, output1: str) -> None:
    """Read the classification dataset CSV, train an SVM classifier, and write results JSON.

    Splits the dataset into training and test sets, trains an SVC classifier,
    evaluates it on the test set, and uploads a JSON file containing model
    accuracy and classification report metrics.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log(f"train_svm: starting — reading {input1} from {folder}")

    # --- Download dataset ---
    local_csv = tempfile.mktemp(suffix=".csv")
    try:
        faasr_get_file(local_file=local_csv, remote_folder=folder, remote_file=input1)
        faasr_log(f"train_svm: downloaded dataset to {local_csv}")

        if not os.path.exists(local_csv) or os.path.getsize(local_csv) == 0:
            msg = f"train_svm: input file {input1} is missing or empty"
            faasr_log(msg)
            raise RuntimeError(msg)

        df = pd.read_csv(local_csv)
        faasr_log(f"train_svm: dataset shape = {df.shape}")
    finally:
        if os.path.exists(local_csv):
            os.remove(local_csv)

    # --- Validate columns ---
    if "target" not in df.columns:
        msg = "train_svm: 'target' column not found in dataset"
        faasr_log(msg)
        raise ValueError(msg)

    feature_cols = [c for c in df.columns if c != "target"]
    if not feature_cols:
        msg = "train_svm: no feature columns found in dataset"
        faasr_log(msg)
        raise ValueError(msg)

    X = df[feature_cols].values
    y = df["target"].values

    # --- Train / test split (80/20, fixed seed for reproducibility) ---
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    faasr_log(
        f"train_svm: train size = {len(X_train)}, test size = {len(X_test)}"
    )

    # --- Train SVM ---
    faasr_log("train_svm: fitting SVC (rbf kernel)")
    clf = SVC(kernel="rbf", random_state=42)
    clf.fit(X_train, y_train)
    faasr_log("train_svm: training complete")

    # --- Evaluate ---
    y_pred = clf.predict(X_test)
    accuracy = float(accuracy_score(y_test, y_pred))
    report_dict = classification_report(y_test, y_pred, output_dict=True)

    faasr_log(f"train_svm: test accuracy = {accuracy:.4f}")

    # --- Build results dict ---
    results = {
        "model": "SVM (SVC, rbf kernel)",
        "accuracy": accuracy,
        "classification_report": report_dict,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_features": int(len(feature_cols)),
    }

    # --- Upload results ---
    local_json = tempfile.mktemp(suffix=".json")
    try:
        with open(local_json, "w") as f:
            json.dump(results, f, indent=2)
        faasr_log(f"train_svm: uploading results to {folder}/{output1}")
        faasr_put_file(local_file=local_json, remote_folder=folder, remote_file=output1)
        faasr_log("train_svm: done")
    finally:
        if os.path.exists(local_json):
            os.remove(local_json)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---