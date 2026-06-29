import json
import os
import tempfile

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input classification dataset CSV must exist in S3 before training can begin")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "random_forest_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Random Forest evaluation metrics JSON was not uploaded to S3 after training")
        raise SystemExit(1)
    if "random_forest_model.joblib" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Serialized Random Forest model was not uploaded to S3 after training")
        raise SystemExit(1)
# --- end contract helpers ---


def train_random_forest(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Download the classification dataset CSV from S3, train a Random Forest
    classifier, evaluate it on a held-out test split, serialize the model,
    and save evaluation metrics as a JSON file back to S3.

    Args:
        folder:  S3 folder prefix for all I/O.
        input1:  Remote filename of the classification dataset CSV
                 (e.g. "classification_dataset.csv").
        output1: Remote filename for the metrics JSON
                 (e.g. "random_forest_metrics.json").
        output2: Remote filename for the serialized model
                 (e.g. "random_forest_model.joblib").
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("train_random_forest: starting Random Forest training")

    # --- Download dataset from S3 ---
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_in:
        local_csv = tmp_in.name

    local_json = None
    local_model = None

    try:
        faasr_log(f"train_random_forest: fetching {input1} from {folder}")
        faasr_get_file(
            local_file=local_csv,
            remote_folder=folder,
            remote_file=input1,
        )

        # --- Load CSV ---
        df = pd.read_csv(local_csv)
        faasr_log(f"train_random_forest: loaded dataset with shape {df.shape}")

        if "label" not in df.columns:
            msg = "train_random_forest: ERROR — 'label' column missing from dataset"
            faasr_log(msg)
            raise ValueError(
                "Required 'label' column not found in classification_dataset.csv"
            )

        feature_cols = [c for c in df.columns if c != "label"]
        X = df[feature_cols].values
        y = df["label"].values

        # --- Train / test split (80 / 20, fixed seed for reproducibility) ---
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        faasr_log(
            f"train_random_forest: split → train={len(X_train)} samples, "
            f"test={len(X_test)} samples"
        )

        # --- Train Random Forest ---
        faasr_log("train_random_forest: fitting RandomForestClassifier")
        clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        clf.fit(X_train, y_train)

        # --- Evaluate on held-out test set ---
        y_pred = clf.predict(X_test)

        metrics = {
            "classifier": "RandomForest",
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(
                y_test, y_pred, average="weighted", zero_division=0
            ),
            "recall": recall_score(
                y_test, y_pred, average="weighted", zero_division=0
            ),
            "f1": f1_score(y_test, y_pred, average="weighted", zero_division=0),
        }
        faasr_log(
            f"train_random_forest: metrics — accuracy={metrics['accuracy']:.4f}, "
            f"precision={metrics['precision']:.4f}, "
            f"recall={metrics['recall']:.4f}, "
            f"f1={metrics['f1']:.4f}"
        )

        # --- Write metrics JSON and upload to S3 ---
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_out:
            local_json = tmp_out.name
            json.dump(metrics, tmp_out, indent=2)

        faasr_log(f"train_random_forest: uploading {output1} to {folder}")
        faasr_put_file(
            local_file=local_json,
            remote_folder=folder,
            remote_file=output1,
        )
        faasr_log("train_random_forest: metrics upload complete")

        # --- Serialize model with joblib and upload to S3 ---
        with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp_model:
            local_model = tmp_model.name

        joblib.dump(clf, local_model)
        faasr_log(f"train_random_forest: uploading {output2} to {folder}")
        faasr_put_file(
            local_file=local_model,
            remote_folder=folder,
            remote_file=output2,
        )
        faasr_log("train_random_forest: model upload complete")

    finally:
        for path in (local_csv, local_json, local_model):
            if path and os.path.exists(path):
                os.remove(path)

    faasr_log("train_random_forest: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---