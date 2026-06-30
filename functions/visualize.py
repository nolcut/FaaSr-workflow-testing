# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "svm_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: SVM metrics JSON 'svm_metrics.json' must exist in S3 before generating the comparison chart")
        raise SystemExit(1)
    if "random_forest_metrics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Random Forest metrics JSON 'random_forest_metrics.json' must exist in S3 before generating the comparison chart")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "model_comparison_chart.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Comparison chart 'model_comparison_chart.png' must be uploaded to S3 after visualization")
        raise SystemExit(1)
# --- end contract helpers ---


def visualize(folder: str, input1: str, input2: str, output1: str) -> None:
    """Compare SVM and Random Forest evaluation metrics in a bar chart.

    Reads the two metrics JSON files produced by ``train_svm`` and
    ``train_random_forest`` from S3, extracts comparable evaluation scores
    (accuracy plus macro-averaged precision/recall/F1), renders a grouped bar
    chart comparing the two models, and uploads the resulting PNG to S3.

    Parameters
    ----------
    folder  : S3 folder where the metrics live and the chart will be written.
    input1  : remote filename of the SVM metrics JSON.
    input2  : remote filename of the Random Forest metrics JSON.
    output1 : remote filename for the comparison chart PNG.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    import json
    import os
    import tempfile

    import numpy as np
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tmp = tempfile.gettempdir()

    # ------------------------------------------------------------------ #
    # 1. Download both metrics JSON files from S3                          #
    # ------------------------------------------------------------------ #
    local_svm = os.path.join(tmp, "visualize_svm_metrics.json")
    local_rf = os.path.join(tmp, "visualize_rf_metrics.json")

    faasr_log(f"visualize: downloading '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_svm, remote_folder=folder, remote_file=input1)

    faasr_log(f"visualize: downloading '{input2}' from folder '{folder}'")
    faasr_get_file(local_file=local_rf, remote_folder=folder, remote_file=input2)

    # ------------------------------------------------------------------ #
    # 2. Load and validate the metrics                                    #
    # ------------------------------------------------------------------ #
    def _load(path, name):
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            msg = f"visualize: metrics file for {name} is missing or empty ({path})"
            faasr_log(msg)
            raise RuntimeError(msg)
        try:
            with open(path) as fh:
                data = json.load(fh)
        except Exception as exc:
            msg = f"visualize: failed to parse JSON metrics for {name}: {exc}"
            faasr_log(msg)
            raise RuntimeError(msg)
        if "accuracy" not in data or "classification_report" not in data:
            msg = (
                f"visualize: metrics for {name} missing expected keys "
                f"'accuracy'/'classification_report' (got keys: {list(data.keys())})"
            )
            faasr_log(msg)
            raise RuntimeError(msg)
        return data

    svm = _load(local_svm, "SVM")
    rf = _load(local_rf, "Random Forest")

    # ------------------------------------------------------------------ #
    # 3. Extract comparable evaluation scores                             #
    # ------------------------------------------------------------------ #
    def _scores(metrics, name):
        report = metrics["classification_report"]
        macro = report.get("macro avg")
        if not isinstance(macro, dict):
            msg = (
                f"visualize: classification_report for {name} missing 'macro avg' "
                f"section (got keys: {list(report.keys())})"
            )
            faasr_log(msg)
            raise RuntimeError(msg)
        return {
            "Accuracy": float(metrics["accuracy"]),
            "Precision": float(macro["precision"]),
            "Recall": float(macro["recall"]),
            "F1-score": float(macro["f1-score"]),
        }

    svm_scores = _scores(svm, "SVM")
    rf_scores = _scores(rf, "Random Forest")

    metric_names = ["Accuracy", "Precision", "Recall", "F1-score"]
    svm_values = [svm_scores[m] for m in metric_names]
    rf_values = [rf_scores[m] for m in metric_names]

    faasr_log(f"visualize: SVM scores = {svm_scores}")
    faasr_log(f"visualize: Random Forest scores = {rf_scores}")

    # ------------------------------------------------------------------ #
    # 4. Build the grouped comparison bar chart                           #
    # ------------------------------------------------------------------ #
    x = np.arange(len(metric_names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars_svm = ax.bar(x - width / 2, svm_values, width, label="SVM", color="#1f77b4")
    bars_rf = ax.bar(x + width / 2, rf_values, width, label="Random Forest", color="#ff7f0e")

    ax.set_title("Model Comparison: SVM vs Random Forest", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Evaluation Metric", fontsize=13)
    ax.set_ylabel("Score", fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels(metric_names, fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=11)
    ax.grid(True, axis="y", linestyle="--", alpha=0.6)

    for bars in (bars_svm, bars_rf):
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.3f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    plt.tight_layout()

    # ------------------------------------------------------------------ #
    # 5. Save and upload the PNG                                          #
    # ------------------------------------------------------------------ #
    local_png = os.path.join(tmp, "visualize_model_comparison_chart.png")
    plt.savefig(local_png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    if not os.path.exists(local_png) or os.path.getsize(local_png) == 0:
        msg = "visualize: rendered comparison chart PNG is missing or empty"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_put_file(local_file=local_png, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize: uploaded comparison chart → '{output1}' in folder '{folder}'")
    faasr_log("visualize: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---