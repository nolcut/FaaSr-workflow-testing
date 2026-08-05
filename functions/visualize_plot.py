import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def visualize_plot(folder: str, input1: str, input2: str, output1: str) -> None:
    local_numbers = "/tmp/random_numbers.json"
    local_mean = "/tmp/mean_value.json"
    faasr_get_file(local_file=local_numbers, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_mean, remote_folder=folder, remote_file=input2)
    with open(local_numbers) as f:
        numbers = json.load(f)
    with open(local_mean) as f:
        mean_data = json.load(f)
    mean = mean_data["mean"]
    fig, ax = plt.subplots()
    ax.hist(numbers, bins=15, color="steelblue", edgecolor="white")
    ax.axvline(mean, color="red", linestyle="--", linewidth=1.5, label=f"Mean: {mean:.4f}")
    ax.set_xlabel("Value")
    ax.set_ylabel("Frequency")
    ax.set_title("Histogram of 100 Random Numbers")
    ax.legend()
    local_out = "/tmp/numbers_plot.png"
    fig.savefig(local_out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved histogram plot to {output1}")
