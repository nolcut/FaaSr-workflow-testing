import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def visualize_results(folder: str, input1: str, input2: str, output1: str) -> None:
    faasr_log(f"Downloading {input1} and {input2} from {folder}")
    local_numbers = "/tmp/random_numbers.json"
    local_stats = "/tmp/statistics.json"
    faasr_get_file(local_file=local_numbers, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_stats, remote_folder=folder, remote_file=input2)

    with open(local_numbers) as f:
        numbers = json.load(f)
    with open(local_stats) as f:
        stats = json.load(f)

    mean = stats["mean"]
    median = stats["median"]
    faasr_log(f"Plotting histogram with mean={mean:.4f}, median={median:.4f}")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(np.array(numbers), bins=20, color="steelblue", edgecolor="white", alpha=0.8)
    ax.axvline(mean, color="red", linewidth=2, label=f"Mean ({mean:.4f})")
    ax.axvline(median, color="orange", linewidth=2, linestyle="--", label=f"Median ({median:.4f})")
    ax.set_xlabel("Value")
    ax.set_ylabel("Frequency")
    ax.set_title("Histogram of 100 Random Numbers (Standard Normal)")
    ax.legend()

    local_output = "/tmp/visualization.png"
    fig.savefig(local_output, dpi=150, bbox_inches="tight")
    plt.close(fig)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log("visualize_results complete")
