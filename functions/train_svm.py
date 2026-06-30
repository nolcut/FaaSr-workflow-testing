import json
import os
import tempfile

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "classification_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input classification dataset 'classification_dataset.csv' must exist in S3 before SVM training can begin")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "svm_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: SVM metrics JSON 'svm_metrics.json' was not found in S3 after training completed")
        raise SystemExit(1)
    if "svm_model.joblib" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Serialised SVM model 'svm_model.joblib' was not found in S3 after training completed")
        raise SystemExit(1)
# --- end contract helpers ---


def train_svm(folder: str, input1: str, output1: str, output2: str) -> None:
    """Train an SVM classifier on the generated classification dataset.

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
    local_csv = os.path.join(tempfile.gettempdir(), "train_svm_input.csv")
    faasr_log(f"train_svm: downloading '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_csv, remote_folder=folder, remote_file=input1)

    # ------------------------------------------------------------------ #
    # 2. Load and validate the dataset                                     #
    # ------------------------------------------------------------------ #
    faasr_log("train_svm: loading dataset")
    df = pd.read_csv(local_csv)

    if "target" not in df.columns:
        msg = f"train_svm: expected column 'target' not found in CSV (columns: {list(df.columns)})"
        faasr_log(msg)
        raise ValueError(msg)

    feature_cols = [c for c in df.columns if c != "target"]
    X = df[feature_cols].values.astype(np.float64)
    y = df["target"].values

    faasr_log(
        f"train_svm: dataset loaded — shape={df.shape}, "
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
        f"train_svm: split — train={len(X_train)}, test={len(X_test)}"
    )

    # ------------------------------------------------------------------ #
    # 4. Train the SVM                                                     #
    # ------------------------------------------------------------------ #
    faasr_log("train_svm: fitting SVC(kernel='rbf', C=1.0)")
    clf = SVC(kernel="rbf", C=1.0, random_state=42)
    clf.fit(X_train, y_train)

    # ------------------------------------------------------------------ #
    # 5. Evaluate                                                          #
    # ------------------------------------------------------------------ #
    y_pred = clf.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))
    report = classification_report(y_test, y_pred, output_dict=True)

    faasr_log(f"train_svm: accuracy={acc:.4f}")

    # ------------------------------------------------------------------ #
    # 6. Save metrics JSON                                                 #
    # ------------------------------------------------------------------ #
    metrics = {
        "accuracy": acc,
        "classification_report": report,
    }
    local_metrics = os.path.join(tempfile.gettempdir(), "train_svm_metrics.json")
    with open(local_metrics, "w") as fh:
        json.dump(metrics, fh, indent=2)
    faasr_log(f"train_svm: metrics written locally → {local_metrics}")

    # ------------------------------------------------------------------ #
    # 7. Save model with joblib                                            #
    # ------------------------------------------------------------------ #
    local_model = os.path.join(tempfile.gettempdir(), "train_svm_model.joblib")
    joblib.dump(clf, local_model)
    faasr_log(f"train_svm: model serialised → {local_model}")

    # ------------------------------------------------------------------ #
    # 8. Upload both artefacts to S3                                       #
    # ------------------------------------------------------------------ #
    faasr_put_file(local_file=local_metrics, remote_folder=folder, remote_file=output1)
    faasr_log(f"train_svm: uploaded metrics → '{output1}' in folder '{folder}'")

    faasr_put_file(local_file=local_model, remote_folder=folder, remote_file=output2)
    faasr_log(f"train_svm: uploaded model → '{output2}' in folder '{folder}'")

    faasr_log("train_svm: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---