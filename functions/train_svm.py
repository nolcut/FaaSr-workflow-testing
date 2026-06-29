import json
import os
import tempfile

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input dataset 'classification_dataset.csv' must exist in S3 before SVM training can begin")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "svm_model.joblib" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Trained SVM model bundle 'svm_model.joblib' must be present in S3 after training completes")
        raise SystemExit(1)
    if "svm_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Performance metrics JSON 'svm_metrics.json' must be present in S3 after training completes")
        raise SystemExit(1)
# --- end contract helpers ---


def train_svm(folder: str, input1: str, output1: str, output2: str) -> None:
    """Read the generated classification dataset CSV from S3, train an SVM
    classifier, evaluate its accuracy, and save the trained model (joblib)
    and performance metrics (JSON) back to S3.

    Args:
        folder:  Remote S3 folder used for all faasr_get/put_file calls.
        input1:  Remote filename of the input CSV (e.g. "classification_dataset.csv").
        output1: Remote filename for the serialised SVM model (e.g. "svm_model.joblib").
        output2: Remote filename for the metrics JSON (e.g. "svm_metrics.json").
    """
    # ------------------------------------------------------------------ #
    # 1. Download the dataset CSV from S3 to a local temp file            #
    # ------------------------------------------------------------------ #
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    tmp_csv_fd, tmp_csv_path = tempfile.mkstemp(suffix=".csv")
    os.close(tmp_csv_fd)

    tmp_model_fd, tmp_model_path = tempfile.mkstemp(suffix=".joblib")
    os.close(tmp_model_fd)

    tmp_metrics_fd, tmp_metrics_path = tempfile.mkstemp(suffix=".json")
    os.close(tmp_metrics_fd)

    try:
        faasr_log(f"train_svm: Downloading '{input1}' from folder '{folder}'")
        faasr_get_file(local_file=tmp_csv_path, remote_folder=folder, remote_file=input1)

        # ------------------------------------------------------------------ #
        # 2. Load and validate the dataset                                    #
        # ------------------------------------------------------------------ #
        df = pd.read_csv(tmp_csv_path)
        faasr_log(f"train_svm: Loaded dataset with shape={df.shape}, columns={list(df.columns)}")

        if "target" not in df.columns:
            msg = f"train_svm: ERROR — 'target' column not found in {input1}; columns are {list(df.columns)}"
            faasr_log(msg)
            raise ValueError(msg)

        feature_cols = [c for c in df.columns if c != "target"]
        if not feature_cols:
            msg = "train_svm: ERROR — no feature columns found in the dataset"
            faasr_log(msg)
            raise ValueError(msg)

        X = df[feature_cols].values
        y = df["target"].values
        faasr_log(f"train_svm: Features={len(feature_cols)}, Samples={len(y)}, Classes={sorted(set(y.tolist()))}")

        # ------------------------------------------------------------------ #
        # 3. Train / test split                                               #
        # ------------------------------------------------------------------ #
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        faasr_log(
            f"train_svm: Split — train_size={len(y_train)}, test_size={len(y_test)}"
        )

        # ------------------------------------------------------------------ #
        # 4. Feature scaling (important for SVM)                             #
        # ------------------------------------------------------------------ #
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # ------------------------------------------------------------------ #
        # 5. Train SVM classifier                                             #
        # ------------------------------------------------------------------ #
        faasr_log("train_svm: Training SVM classifier (RBF kernel, C=1.0, gamma='scale')")
        clf = SVC(kernel="rbf", C=1.0, gamma="scale", random_state=42)
        clf.fit(X_train_scaled, y_train)
        faasr_log("train_svm: Training complete")

        # ------------------------------------------------------------------ #
        # 6. Evaluate                                                         #
        # ------------------------------------------------------------------ #
        y_pred = clf.predict(X_test_scaled)
        accuracy = float(accuracy_score(y_test, y_pred))
        report = classification_report(y_test, y_pred, output_dict=True)
        faasr_log(f"train_svm: Test accuracy={accuracy:.4f}")

        # ------------------------------------------------------------------ #
        # 7. Bundle model + scaler together so the scaler travels with it     #
        # ------------------------------------------------------------------ #
        model_bundle = {"classifier": clf, "scaler": scaler, "feature_cols": feature_cols}

        # ------------------------------------------------------------------ #
        # 8. Serialise model to joblib temp file and upload                   #
        # ------------------------------------------------------------------ #
        joblib.dump(model_bundle, tmp_model_path)
        faasr_log(f"train_svm: Uploading model '{output1}' to folder '{folder}'")
        faasr_put_file(local_file=tmp_model_path, remote_folder=folder, remote_file=output1)

        # ------------------------------------------------------------------ #
        # 9. Write metrics JSON temp file and upload                          #
        # ------------------------------------------------------------------ #
        metrics = {
            "model": "SVM",
            "kernel": "rbf",
            "C": 1.0,
            "gamma": "scale",
            "accuracy": accuracy,
            "train_size": int(len(y_train)),
            "test_size": int(len(y_test)),
            "n_features": int(len(feature_cols)),
            "classification_report": report,
        }
        with open(tmp_metrics_path, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2)

        faasr_log(f"train_svm: Uploading metrics '{output2}' to folder '{folder}'")
        faasr_put_file(local_file=tmp_metrics_path, remote_folder=folder, remote_file=output2)

        faasr_log(
            f"train_svm: Done — accuracy={accuracy:.4f}, "
            f"model='{output1}', metrics='{output2}'"
        )

    finally:
        for p in (tmp_csv_path, tmp_model_path, tmp_metrics_path):
            if os.path.exists(p):
                os.remove(p)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---