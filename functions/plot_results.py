import json
import os
import tempfile

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless environments
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "random_numbers.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file random_numbers.csv must exist in S3 before plot_results can generate the histogram")
        raise SystemExit(1)
    if "statistics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file statistics.json must exist in S3 before plot_results can overlay mean and std deviation on the histogram")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "random_numbers_histogram.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output histogram PNG random_numbers_histogram.png was not found in S3 after plot_results completed")
        raise SystemExit(1)
# --- end contract helpers ---


def plot_results(folder: str, input1: str, input2: str, output1: str) -> None:
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("Starting plot_results")

    tmp_csv_path = None
    tmp_json_path = None
    tmp_png_path = None

    try:
        # --- Download random numbers CSV ---
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp_csv:
            tmp_csv_path = tmp_csv.name

        faasr_get_file(local_file=tmp_csv_path, remote_folder=folder, remote_file=input1)
        faasr_log(f"Downloaded {input1} from folder {folder}")

        df = pd.read_csv(tmp_csv_path)
        if "value" not in df.columns:
            msg = f"Expected column 'value' in {input1}, got columns: {list(df.columns)}"
            faasr_log(msg)
            raise ValueError(msg)

        values = df["value"].to_numpy(dtype=float)
        faasr_log(f"Loaded {len(values)} values from {input1}")

        # --- Download statistics JSON ---
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp_json:
            tmp_json_path = tmp_json.name

        faasr_get_file(local_file=tmp_json_path, remote_folder=folder, remote_file=input2)
        faasr_log(f"Downloaded {input2} from folder {folder}")

        with open(tmp_json_path, "r") as f:
            stats = json.load(f)

        if "mean" not in stats or "std" not in stats:
            msg = f"Expected keys 'mean' and 'std' in {input2}, got: {list(stats.keys())}"
            faasr_log(msg)
            raise ValueError(msg)

        mean = float(stats["mean"])
        std = float(stats["std"])
        faasr_log(f"Loaded statistics: mean={mean:.6f}, std={std:.6f}")

        # --- Produce histogram plot ---
        fig, ax = plt.subplots(figsize=(8, 5))

        ax.hist(values, bins=15, color="steelblue", edgecolor="white", alpha=0.8, label="Random numbers")

        # Vertical line for mean
        ax.axvline(x=mean, color="red", linestyle="--", linewidth=2, label=f"Mean = {mean:.4f}")

        # Vertical lines for ±1 std deviation
        ax.axvline(
            x=mean + std,
            color="orange",
            linestyle=":",
            linewidth=2,
            label=f"Mean + SD = {mean + std:.4f}",
        )
        ax.axvline(
            x=mean - std,
            color="orange",
            linestyle=":",
            linewidth=2,
            label=f"Mean − SD = {mean - std:.4f}",
        )

        ax.set_xlabel("Value")
        ax.set_ylabel("Frequency")
        ax.set_title("Histogram of 100 Random Numbers (Standard Normal)")
        ax.legend(loc="upper right")
        fig.tight_layout()

        # --- Save PNG to temp file and upload ---
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_png:
            tmp_png_path = tmp_png.name

        fig.savefig(tmp_png_path, dpi=150, format="png")
        plt.close(fig)
        faasr_log(f"Saved histogram to temporary file; uploading as {output1}")

        faasr_put_file(local_file=tmp_png_path, remote_folder=folder, remote_file=output1)
        faasr_log(f"Successfully uploaded {output1} to folder {folder}")

    finally:
        for p in (tmp_csv_path, tmp_json_path, tmp_png_path):
            if p and os.path.exists(p):
                os.remove(p)

    faasr_log("plot_results complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---