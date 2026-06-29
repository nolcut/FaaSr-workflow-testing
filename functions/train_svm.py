import json
import os
import tempfile

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input classification dataset CSV must exist in S3 before SVM training can begin")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "svm_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: SVM metrics JSON output must exist in S3 after training and evaluation completes")
        raise SystemExit(1)
# --- end contract helpers ---


def train_svm(folder: str, input1: str, output1: str) -> None:
    """
    Download the classification dataset CSV from S3, train an SVM classifier,
    evaluate it on a held-out test split, and save accuracy, precision, recall,
    and F1 score as a JSON file back to S3.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("train_svm: starting SVM training")

    # --- Download dataset from S3 ---
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_in:
        local_csv = tmp_in.name

    try:
        faasr_log(f"train_svm: fetching {input1} from {folder}")
        faasr_get_file(
            local_file=local_csv,
            remote_folder=folder,
            remote_file=input1,
        )

        # --- Load CSV ---
        df = pd.read_csv(local_csv)
        faasr_log(f"train_svm: loaded dataset with shape {df.shape}")

        if "label" not in df.columns:
            faasr_log("train_svm: ERROR — 'label' column missing from dataset")
            raise ValueError("Required 'label' column not found in classification_dataset.csv")

        feature_cols = [c for c in df.columns if c != "label"]
        X = df[feature_cols].values
        y = df["label"].values

        # --- Train / test split (80 / 20, fixed seed for reproducibility) ---
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        faasr_log(
            f"train_svm: split → train={len(X_train)} samples, test={len(X_test)} samples"
        )

        # --- Train SVM ---
        faasr_log("train_svm: fitting SVC (RBF kernel)")
        clf = SVC(kernel="rbf", random_state=42)
        clf.fit(X_train, y_train)

        # --- Evaluate on held-out test set ---
        y_pred = clf.predict(X_test)

        metrics = {
            "classifier": "SVM",
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, average="weighted", zero_division=0),
            "recall": recall_score(y_test, y_pred, average="weighted", zero_division=0),
            "f1": f1_score(y_test, y_pred, average="weighted", zero_division=0),
        }
        faasr_log(
            f"train_svm: metrics — accuracy={metrics['accuracy']:.4f}, "
            f"precision={metrics['precision']:.4f}, recall={metrics['recall']:.4f}, "
            f"f1={metrics['f1']:.4f}"
        )

        # --- Write metrics JSON and upload to S3 ---
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_out:
            local_json = tmp_out.name
            json.dump(metrics, tmp_out, indent=2)

        try:
            faasr_log(f"train_svm: uploading {output1} to {folder}")
            faasr_put_file(
                local_file=local_json,
                remote_folder=folder,
                remote_file=output1,
            )
            faasr_log("train_svm: upload complete")
        finally:
            if os.path.exists(local_json):
                os.remove(local_json)

    finally:
        if os.path.exists(local_csv):
            os.remove(local_csv)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---