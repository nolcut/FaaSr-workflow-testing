import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_results():
    invocation_id = faasr_invocation_id()

    faasr_get_file(
        local_file="samples.csv",
        remote_file="samples.csv",
        local_folder="/tmp",
        remote_folder=f"generator-demo/{invocation_id}",
    )

    xs, ys, labels = [], [], []
    with open("/tmp/samples.csv") as f:
        for row in csv.DictReader(f):
            xs.append(float(row["x"]))
            ys.append(float(row["y"]))
            labels.append(row["label"])

    curve_x = [i / 100.0 for i in range(0, 301)]
    curve_y = [v ** 2 for v in curve_x]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(curve_x, curve_y, color="gray", linestyle="--", linewidth=1, label="y = x²")
    ax.scatter(xs, ys, color="steelblue", s=120, zorder=3)
    for x, y, lbl in zip(xs, ys, labels):
        ax.annotate(lbl, (x, y), textcoords="offset points", xytext=(6, 4), fontsize=11)

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Generator Demo: parallel samples on y = x²")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig("/tmp/plot.png", dpi=150)

    faasr_put_file(
        local_file="plot.png",
        remote_file="plot.png",
        local_folder="/tmp",
        remote_folder=f"generator-demo/{invocation_id}",
    )
    faasr_log(f"Plot saved: generator-demo/{invocation_id}/plot.png")
