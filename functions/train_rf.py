import json
import os
import tempfile

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input dataset 'classification_dataset.csv' must exist in S3 before train_rf can download and train on it")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "rf_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output metrics file 'rf_metrics.json' must exist in S3 after train_rf completes model training and evaluation")
        raise SystemExit(1)
# --- end contract helpers ---


def train_rf(folder: str, input1: str, output1: str) -> None:
    """Read the generated classification dataset CSV from S3, train a Random
    Forest classifier, evaluate its performance, and save the evaluation
    metrics as a JSON file to S3.

    Args:
        folder:  Remote S3 folder used for all faasr_get/put_file calls.
        input1:  Remote filename of the input CSV (e.g. "classification_dataset.csv").
        output1: Remote filename for the metrics JSON (e.g. "rf_metrics.json").
    """
    # ------------------------------------------------------------------ #
    # 1. Download the dataset CSV from S3 to a local temp file            #
    # ------------------------------------------------------------------ #
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    tmp_csv_fd, tmp_csv_path = tempfile.mkstemp(suffix=".csv")
    os.close(tmp_csv_fd)

    tmp_metrics_fd, tmp_metrics_path = tempfile.mkstemp(suffix=".json")
    os.close(tmp_metrics_fd)

    try:
        faasr_log(f"train_rf: Downloading '{input1}' from folder '{folder}'")
        faasr_get_file(local_file=tmp_csv_path, remote_folder=folder, remote_file=input1)

        # ------------------------------------------------------------------ #
        # 2. Load and validate the dataset                                    #
        # ------------------------------------------------------------------ #
        df = pd.read_csv(tmp_csv_path)
        faasr_log(f"train_rf: Loaded dataset with shape={df.shape}, columns={list(df.columns)}")

        if "target" not in df.columns:
            msg = (
                f"train_rf: ERROR — 'target' column not found in {input1}; "
                f"columns are {list(df.columns)}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        feature_cols = [c for c in df.columns if c != "target"]
        if not feature_cols:
            msg = "train_rf: ERROR — no feature columns found in the dataset"
            faasr_log(msg)
            raise ValueError(msg)

        X = df[feature_cols].values
        y = df["target"].values
        faasr_log(
            f"train_rf: Features={len(feature_cols)}, Samples={len(y)}, "
            f"Classes={sorted(set(y.tolist()))}"
        )

        # ------------------------------------------------------------------ #
        # 3. Train / test split                                               #
        # ------------------------------------------------------------------ #
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        faasr_log(
            f"train_rf: Split — train_size={len(y_train)}, test_size={len(y_test)}"
        )

        # ------------------------------------------------------------------ #
        # 4. Train Random Forest classifier                                   #
        # ------------------------------------------------------------------ #
        faasr_log(
            "train_rf: Training RandomForestClassifier "
            "(n_estimators=100, random_state=42)"
        )
        clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        clf.fit(X_train, y_train)
        faasr_log("train_rf: Training complete")

        # ------------------------------------------------------------------ #
        # 5. Evaluate                                                         #
        # ------------------------------------------------------------------ #
        y_pred = clf.predict(X_test)
        accuracy = float(accuracy_score(y_test, y_pred))
        precision = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
        recall = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
        f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
        report = classification_report(y_test, y_pred, output_dict=True)

        faasr_log(
            f"train_rf: Test accuracy={accuracy:.4f}, precision={precision:.4f}, "
            f"recall={recall:.4f}, f1={f1:.4f}"
        )

        # ------------------------------------------------------------------ #
        # 6. Write metrics JSON temp file and upload                          #
        # ------------------------------------------------------------------ #
        metrics = {
            "model": "RandomForest",
            "n_estimators": 100,
            "random_state": 42,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "train_size": int(len(y_train)),
            "test_size": int(len(y_test)),
            "n_features": int(len(feature_cols)),
            "classification_report": report,
        }
        with open(tmp_metrics_path, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2)

        faasr_log(f"train_rf: Uploading metrics '{output1}' to folder '{folder}'")
        faasr_put_file(local_file=tmp_metrics_path, remote_folder=folder, remote_file=output1)

        faasr_log(
            f"train_rf: Done — accuracy={accuracy:.4f}, "
            f"precision={precision:.4f}, recall={recall:.4f}, f1={f1:.4f}, "
            f"metrics='{output1}'"
        )

    finally:
        for p in (tmp_csv_path, tmp_metrics_path):
            if os.path.exists(p):
                os.remove(p)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---