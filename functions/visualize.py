import json
import os
import tempfile

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — no display required
import matplotlib.pyplot as plt
import numpy as np


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "svm_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: SVM metrics JSON must exist in S3 before visualization can proceed")
        raise SystemExit(1)
    if "random_forest_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Random Forest metrics JSON must exist in S3 before visualization can proceed")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "classifier_comparison.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Classifier comparison chart PNG must have been uploaded to S3 after visualization completes")
        raise SystemExit(1)
# --- end contract helpers ---


def visualize(folder: str, input1: str, input2: str, output1: str) -> None:
    """Read SVM and Random Forest metrics from S3, then produce a grouped bar
    chart comparing accuracy, precision, recall, and F1-score.

    Parameters
    ----------
    folder  : S3 folder where inputs live and the output will be written.
    input1  : remote filename of the SVM metrics JSON (e.g. 'svm_metrics.json').
    input2  : remote filename of the Random Forest metrics JSON
              (e.g. 'random_forest_metrics.json').
    output1 : remote filename for the comparison PNG chart
              (e.g. 'classifier_comparison.png').
    """

    # ------------------------------------------------------------------ #
    # 1. Download metrics JSON files from S3                               #
    # ------------------------------------------------------------------ #
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    local_svm_metrics = os.path.join(tempfile.gettempdir(), "visualize_svm_metrics.json")
    local_rf_metrics = os.path.join(tempfile.gettempdir(), "visualize_rf_metrics.json")

    faasr_log(f"visualize: downloading '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_svm_metrics, remote_folder=folder, remote_file=input1)

    faasr_log(f"visualize: downloading '{input2}' from folder '{folder}'")
    faasr_get_file(local_file=local_rf_metrics, remote_folder=folder, remote_file=input2)

    # ------------------------------------------------------------------ #
    # 2. Parse JSON files                                                  #
    # ------------------------------------------------------------------ #
    faasr_log("visualize: parsing SVM metrics")
    with open(local_svm_metrics, "r") as fh:
        svm_data = json.load(fh)

    faasr_log("visualize: parsing Random Forest metrics")
    with open(local_rf_metrics, "r") as fh:
        rf_data = json.load(fh)

    # ------------------------------------------------------------------ #
    # 3. Extract the four comparison metrics from each JSON                #
    #                                                                      #
    # Both upstream functions produce:                                     #
    #   {                                                                  #
    #     "accuracy": <float>,                                             #
    #     "classification_report": {                                       #
    #       ...,                                                           #
    #       "weighted avg": {                                              #
    #         "precision": <float>,                                        #
    #         "recall": <float>,                                           #
    #         "f1-score": <float>,                                         #
    #         "support": <int>                                             #
    #       },                                                             #
    #       ...                                                            #
    #     }                                                                #
    #   }                                                                  #
    # We use the top-level "accuracy" field and "weighted avg" for         #
    # precision / recall / F1.                                             #
    # ------------------------------------------------------------------ #
    def _extract_metrics(data: dict, label: str) -> dict:
        if "accuracy" not in data:
            msg = f"visualize: key 'accuracy' missing in {label} metrics JSON"
            faasr_log(msg)
            raise KeyError(msg)
        if "classification_report" not in data:
            msg = f"visualize: key 'classification_report' missing in {label} metrics JSON"
            faasr_log(msg)
            raise KeyError(msg)

        report = data["classification_report"]
        avg_key = "weighted avg"
        if avg_key not in report:
            msg = f"visualize: key '{avg_key}' missing in {label} classification_report"
            faasr_log(msg)
            raise KeyError(msg)

        wavg = report[avg_key]
        return {
            "accuracy":  float(data["accuracy"]),
            "precision": float(wavg["precision"]),
            "recall":    float(wavg["recall"]),
            "f1-score":  float(wavg["f1-score"]),
        }

    svm_metrics = _extract_metrics(svm_data, "SVM")
    rf_metrics  = _extract_metrics(rf_data,  "Random Forest")

    faasr_log(
        f"visualize: SVM      — accuracy={svm_metrics['accuracy']:.4f}, "
        f"precision={svm_metrics['precision']:.4f}, "
        f"recall={svm_metrics['recall']:.4f}, "
        f"f1={svm_metrics['f1-score']:.4f}"
    )
    faasr_log(
        f"visualize: RF       — accuracy={rf_metrics['accuracy']:.4f}, "
        f"precision={rf_metrics['precision']:.4f}, "
        f"recall={rf_metrics['recall']:.4f}, "
        f"f1={rf_metrics['f1-score']:.4f}"
    )

    # ------------------------------------------------------------------ #
    # 4. Build the grouped bar chart                                       #
    # ------------------------------------------------------------------ #
    metric_names = ["Accuracy", "Precision", "Recall", "F1-Score"]
    metric_keys  = ["accuracy", "precision", "recall", "f1-score"]

    svm_values = [svm_metrics[k] for k in metric_keys]
    rf_values  = [rf_metrics[k]  for k in metric_keys]

    x = np.arange(len(metric_names))
    bar_width = 0.35

    fig, ax = plt.subplots(figsize=(9, 6))

    bars_svm = ax.bar(x - bar_width / 2, svm_values, bar_width,
                      label="SVM", color="#4C72B0", edgecolor="white", linewidth=0.7)
    bars_rf  = ax.bar(x + bar_width / 2, rf_values,  bar_width,
                      label="Random Forest", color="#DD8452", edgecolor="white", linewidth=0.7)

    # Annotate bars with their numeric values
    for bar in bars_svm:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.005,
            f"{bar.get_height():.3f}",
            ha="center", va="bottom", fontsize=8, color="#4C72B0"
        )
    for bar in bars_rf:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.005,
            f"{bar.get_height():.3f}",
            ha="center", va="bottom", fontsize=8, color="#DD8452"
        )

    ax.set_xticks(x)
    ax.set_xticklabels(metric_names, fontsize=11)
    ax.set_ylim(0.0, 1.15)
    ax.set_ylabel("Score", fontsize=12)
    ax.set_title("SVM vs Random Forest — Classifier Performance Comparison", fontsize=13, pad=14)
    ax.legend(fontsize=11)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    fig.tight_layout()

    # ------------------------------------------------------------------ #
    # 5. Save chart locally then upload to S3                              #
    # ------------------------------------------------------------------ #
    local_png = os.path.join(tempfile.gettempdir(), "visualize_classifier_comparison.png")
    fig.savefig(local_png, dpi=150, format="png")
    plt.close(fig)
    faasr_log(f"visualize: chart saved locally → {local_png}")

    faasr_put_file(local_file=local_png, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize: uploaded chart → '{output1}' in folder '{folder}'")

    faasr_log("visualize: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---