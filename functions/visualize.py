import json
import os
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "svm_results.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: SVM results file must be present in S3 before visualization can proceed")
        raise SystemExit(1)
    if "rf_results.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Random Forest results file must be present in S3 before visualization can proceed")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "model_comparison.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Model comparison bar chart PNG must be uploaded to S3 after visualization completes")
        raise SystemExit(1)
# --- end contract helpers ---


def visualize(folder: str, input1: str, input2: str, output1: str) -> None:
    """Download SVM and Random Forest results JSON files, generate a bar chart
    comparing model accuracies, and upload the PNG plot to S3.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("visualize: starting — downloading model result files")

    # --- Download SVM results ---
    local_svm = tempfile.mktemp(suffix=".json")
    try:
        faasr_get_file(local_file=local_svm, remote_folder=folder, remote_file=input1)
        faasr_log(f"visualize: downloaded {input1}")

        if not os.path.exists(local_svm) or os.path.getsize(local_svm) == 0:
            msg = f"visualize: input file {input1} is missing or empty"
            faasr_log(msg)
            raise RuntimeError(msg)

        with open(local_svm, "r") as f:
            svm_results = json.load(f)
    finally:
        if os.path.exists(local_svm):
            os.remove(local_svm)

    # --- Download Random Forest results ---
    local_rf = tempfile.mktemp(suffix=".json")
    try:
        faasr_get_file(local_file=local_rf, remote_folder=folder, remote_file=input2)
        faasr_log(f"visualize: downloaded {input2}")

        if not os.path.exists(local_rf) or os.path.getsize(local_rf) == 0:
            msg = f"visualize: input file {input2} is missing or empty"
            faasr_log(msg)
            raise RuntimeError(msg)

        with open(local_rf, "r") as f:
            rf_results = json.load(f)
    finally:
        if os.path.exists(local_rf):
            os.remove(local_rf)

    # --- Validate required keys ---
    for name, data in [("SVM", svm_results), ("Random Forest", rf_results)]:
        if "accuracy" not in data:
            msg = f"visualize: 'accuracy' key missing from {name} results"
            faasr_log(msg)
            raise KeyError(msg)
        if "model" not in data:
            msg = f"visualize: 'model' key missing from {name} results"
            faasr_log(msg)
            raise KeyError(msg)

    svm_accuracy = float(svm_results["accuracy"])
    rf_accuracy = float(rf_results["accuracy"])
    svm_label = svm_results["model"]
    rf_label = rf_results["model"]

    faasr_log(f"visualize: SVM accuracy = {svm_accuracy:.4f}, RF accuracy = {rf_accuracy:.4f}")

    # --- Optionally extract macro-avg F1 for additional annotation ---
    svm_f1 = None
    rf_f1 = None
    if "classification_report" in svm_results:
        svm_f1 = svm_results["classification_report"].get("macro avg", {}).get("f1-score")
    if "classification_report" in rf_results:
        rf_f1 = rf_results["classification_report"].get("macro avg", {}).get("f1-score")

    # --- Generate bar chart ---
    models = [svm_label, rf_label]
    accuracies = [svm_accuracy, rf_accuracy]

    fig, ax = plt.subplots(figsize=(9, 6))

    colors = ["#4C72B0", "#DD8452"]
    bars = ax.bar(models, accuracies, color=colors, width=0.5, edgecolor="black", linewidth=0.8)

    # Annotate bars with accuracy values
    for bar, acc in zip(bars, accuracies):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + 0.005,
            f"{acc:.4f}",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
        )

    # Optionally annotate with macro-avg F1 below bar top
    f1_values = [svm_f1, rf_f1]
    for bar, f1 in zip(bars, f1_values):
        if f1 is not None:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height() / 2.0,
                f"F1: {float(f1):.4f}",
                ha="center",
                va="center",
                fontsize=10,
                color="white",
                fontweight="bold",
            )

    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Accuracy", fontsize=13)
    ax.set_title("Model Accuracy Comparison: SVM vs Random Forest", fontsize=14, fontweight="bold")
    ax.set_xlabel("Model", fontsize=13)

    # Add a horizontal reference line at 0.5 (random baseline)
    ax.axhline(y=0.5, color="gray", linestyle="--", linewidth=1, label="Random baseline (0.5)")
    ax.legend(fontsize=10)

    ax.yaxis.grid(True, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)

    plt.tight_layout()

    # --- Save and upload plot ---
    local_png = tempfile.mktemp(suffix=".png")
    try:
        fig.savefig(local_png, dpi=150, bbox_inches="tight")
        plt.close(fig)
        faasr_log(f"visualize: plot saved locally at {local_png}")

        if not os.path.exists(local_png) or os.path.getsize(local_png) == 0:
            msg = "visualize: failed to write PNG file"
            faasr_log(msg)
            raise RuntimeError(msg)

        faasr_log(f"visualize: uploading {output1} to {folder}")
        faasr_put_file(local_file=local_png, remote_folder=folder, remote_file=output1)
        faasr_log("visualize: done — model comparison chart uploaded")
    finally:
        if os.path.exists(local_png):
            os.remove(local_png)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---