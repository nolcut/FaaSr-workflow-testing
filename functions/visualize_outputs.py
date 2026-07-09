import math

import matplotlib
matplotlib.use("Agg")  # headless / non-GUI backend (no display in the container)
import matplotlib.pyplot as plt
import pandas as pd


def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    faasr_log(f"visualize_outputs: reading simulation output '{input1}' from folder '{folder}'")

    # Fetch the PyADM1 dynamic simulation results from S3 (bare basename).
    local_csv = "dynamic_out_local.csv"
    faasr_get_file(local_file=local_csv, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_csv)
    if df.shape[0] == 0 or df.shape[1] == 0:
        msg = f"visualize_outputs: '{input1}' is empty or unreadable ({df.shape}); cannot plot"
        faasr_log(msg)
        raise ValueError(msg)
    faasr_log(f"visualize_outputs: loaded {df.shape[0]} time steps x {df.shape[1]} variables")

    # dynamic_out.csv holds one column per ADM1 state variable and one row per
    # simulation step (the model writes it with index=False and no explicit time
    # column), so the x-axis is the simulation step index.
    steps = range(len(df))
    columns = list(df.columns)

    ncols = 5
    nrows = math.ceil(len(columns) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows), squeeze=False)

    for idx, col in enumerate(columns):
        ax = axes[idx // ncols][idx % ncols]
        series = pd.to_numeric(df[col], errors="coerce")
        ax.plot(steps, series, marker="o", markersize=3, linewidth=1.2, color="tab:blue")
        ax.set_title(col, fontsize=9)
        ax.set_xlabel("simulation step", fontsize=7)
        ax.tick_params(labelsize=6)
        ax.grid(True, alpha=0.3)

    # Hide any unused subplot slots in the final row.
    for empty in range(len(columns), nrows * ncols):
        axes[empty // ncols][empty % ncols].axis("off")

    fig.suptitle("PyADM1 digester simulation — evolution of state variables",
                 fontsize=14, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.98])

    local_png = "simulation_plots_local.png"
    fig.savefig(local_png, dpi=120)
    plt.close(fig)

    faasr_put_file(local_file=local_png, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_outputs: wrote figure with {len(columns)} panels to '{output1}'")
