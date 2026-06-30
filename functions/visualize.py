import json
import os
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "svm_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: SVM metrics JSON must be present in S3 before visualization can proceed")
        raise SystemExit(1)
    if "random_forest_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Random Forest metrics JSON must be present in S3 before visualization can proceed")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "accuracy_comparison.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Accuracy comparison bar chart PNG was not uploaded to S3")
        raise SystemExit(1)
    if "svm_report_heatmap.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: SVM classification report heatmap PNG was not uploaded to S3")
        raise SystemExit(1)
    if "random_forest_report_heatmap.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Random Forest classification report heatmap PNG was not uploaded to S3")
        raise SystemExit(1)
# --- end contract helpers ---


def visualize(folder: str, input1: str, input2: str, output1: str, output2: str, output3: str) -> None:
    """Compare SVM and Random Forest evaluation metrics visually.

    Parameters
    ----------
    folder  : S3 folder where inputs live and outputs will be written.
    input1  : remote filename of the SVM metrics JSON (produced by train_svm).
    input2  : remote filename of the Random Forest metrics JSON (produced by train_random_forest).
    output1 : remote filename for the accuracy comparison bar chart PNG.
    output2 : remote filename for the SVM classification report heatmap PNG.
    output3 : remote filename for the Random Forest classification report heatmap PNG.
    """

    # ------------------------------------------------------------------ #
    # 1. Download metrics JSON files from S3                               #
    # ------------------------------------------------------------------ #
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    local_svm_metrics = os.path.join(tempfile.gettempdir(), "visualize_svm_metrics.json")
    faasr_log(f"visualize: downloading '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_svm_metrics, remote_folder=folder, remote_file=input1)

    local_rf_metrics = os.path.join(tempfile.gettempdir(), "visualize_rf_metrics.json")
    faasr_log(f"visualize: downloading '{input2}' from folder '{folder}'")
    faasr_get_file(local_file=local_rf_metrics, remote_folder=folder, remote_file=input2)

    # ------------------------------------------------------------------ #
    # 2. Parse metrics                                                      #
    # ------------------------------------------------------------------ #
    faasr_log("visualize: parsing SVM metrics")
    with open(local_svm_metrics, "r") as fh:
        svm_data = json.load(fh)

    if "accuracy" not in svm_data or "classification_report" not in svm_data:
        msg = f"visualize: SVM metrics JSON missing required keys 'accuracy' and/or 'classification_report' (keys found: {list(svm_data.keys())})"
        faasr_log(msg)
        raise ValueError(msg)

    svm_accuracy = float(svm_data["accuracy"])
    svm_report = svm_data["classification_report"]

    faasr_log("visualize: parsing Random Forest metrics")
    with open(local_rf_metrics, "r") as fh:
        rf_data = json.load(fh)

    if "accuracy" not in rf_data or "classification_report" not in rf_data:
        msg = f"visualize: RF metrics JSON missing required keys 'accuracy' and/or 'classification_report' (keys found: {list(rf_data.keys())})"
        faasr_log(msg)
        raise ValueError(msg)

    rf_accuracy = float(rf_data["accuracy"])
    rf_report = rf_data["classification_report"]

    faasr_log(f"visualize: SVM accuracy={svm_accuracy:.4f}, RF accuracy={rf_accuracy:.4f}")

    # ------------------------------------------------------------------ #
    # 3. Build per-class DataFrames for heatmaps                           #
    #    Skip summary rows (accuracy scalar, macro avg, weighted avg)      #
    # ------------------------------------------------------------------ #
    _SUMMARY_KEYS = {"accuracy", "macro avg", "weighted avg"}
    _METRIC_COLS = ["precision", "recall", "f1-score"]

    def _report_to_df(report: dict) -> pd.DataFrame:
        rows = {}
        for label, values in report.items():
            if label in _SUMMARY_KEYS:
                continue
            if not isinstance(values, dict):
                continue
            rows[str(label)] = {col: float(values[col]) for col in _METRIC_COLS if col in values}
        if not rows:
            msg = "visualize: classification report contains no per-class entries"
            faasr_log(msg)
            raise ValueError(msg)
        return pd.DataFrame(rows, index=_METRIC_COLS).T  # shape: (n_classes, 3)

    svm_df = _report_to_df(svm_report)
    rf_df = _report_to_df(rf_report)

    faasr_log(f"visualize: SVM report shape={svm_df.shape}, RF report shape={rf_df.shape}")

    # ------------------------------------------------------------------ #
    # 4. Output 1 — accuracy comparison bar chart                          #
    # ------------------------------------------------------------------ #
    local_acc_chart = os.path.join(tempfile.gettempdir(), "visualize_accuracy_comparison.png")
    faasr_log("visualize: creating accuracy comparison bar chart")

    fig, ax = plt.subplots(figsize=(6, 5))
    classifiers = ["SVM", "Random Forest"]
    accuracies = [svm_accuracy, rf_accuracy]
    bar_colors = ["steelblue", "darkorange"]
    bars = ax.bar(classifiers, accuracies, color=bar_colors, width=0.4, edgecolor="black")

    for bar, val in zip(bars, accuracies):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + 0.005,
            f"{val:.4f}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    ax.set_ylim(0, min(1.05, max(accuracies) + 0.1))
    ax.set_ylabel("Accuracy", fontsize=12)
    ax.set_title("Classifier Accuracy Comparison", fontsize=14, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(local_acc_chart, dpi=150)
    plt.close(fig)
    faasr_log(f"visualize: accuracy chart saved → {local_acc_chart}")

    # ------------------------------------------------------------------ #
    # 5. Output 2 — SVM classification report heatmap                     #
    # ------------------------------------------------------------------ #
    local_svm_heatmap = os.path.join(tempfile.gettempdir(), "visualize_svm_report_heatmap.png")
    faasr_log("visualize: creating SVM classification report heatmap")

    fig, ax = plt.subplots(figsize=(max(5, len(_METRIC_COLS) * 1.5), max(4, len(svm_df) * 0.6 + 1.5)))
    sns.heatmap(
        svm_df,
        annot=True,
        fmt=".3f",
        cmap="Blues",
        vmin=0.0,
        vmax=1.0,
        linewidths=0.5,
        linecolor="lightgray",
        ax=ax,
    )
    ax.set_title("SVM Classification Report", fontsize=13, fontweight="bold")
    ax.set_xlabel("Metric", fontsize=11)
    ax.set_ylabel("Class", fontsize=11)
    fig.tight_layout()
    fig.savefig(local_svm_heatmap, dpi=150)
    plt.close(fig)
    faasr_log(f"visualize: SVM heatmap saved → {local_svm_heatmap}")

    # ------------------------------------------------------------------ #
    # 6. Output 3 — Random Forest classification report heatmap           #
    # ------------------------------------------------------------------ #
    local_rf_heatmap = os.path.join(tempfile.gettempdir(), "visualize_rf_report_heatmap.png")
    faasr_log("visualize: creating Random Forest classification report heatmap")

    fig, ax = plt.subplots(figsize=(max(5, len(_METRIC_COLS) * 1.5), max(4, len(rf_df) * 0.6 + 1.5)))
    sns.heatmap(
        rf_df,
        annot=True,
        fmt=".3f",
        cmap="Oranges",
        vmin=0.0,
        vmax=1.0,
        linewidths=0.5,
        linecolor="lightgray",
        ax=ax,
    )
    ax.set_title("Random Forest Classification Report", fontsize=13, fontweight="bold")
    ax.set_xlabel("Metric", fontsize=11)
    ax.set_ylabel("Class", fontsize=11)
    fig.tight_layout()
    fig.savefig(local_rf_heatmap, dpi=150)
    plt.close(fig)
    faasr_log(f"visualize: RF heatmap saved → {local_rf_heatmap}")

    # ------------------------------------------------------------------ #
    # 7. Upload all three PNGs to S3                                       #
    # ------------------------------------------------------------------ #
    faasr_put_file(local_file=local_acc_chart, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize: uploaded accuracy chart → '{output1}' in folder '{folder}'")

    faasr_put_file(local_file=local_svm_heatmap, remote_folder=folder, remote_file=output2)
    faasr_log(f"visualize: uploaded SVM heatmap → '{output2}' in folder '{folder}'")

    faasr_put_file(local_file=local_rf_heatmap, remote_folder=folder, remote_file=output3)
    faasr_log(f"visualize: uploaded RF heatmap → '{output3}' in folder '{folder}'")

    faasr_log("visualize: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---