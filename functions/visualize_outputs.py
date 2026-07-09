import math

import matplotlib
# Force a headless, non-interactive backend before importing pyplot so this
# runs in a container with no display server.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    faasr_log("visualize_outputs: starting for folder '%s' (input '%s')" % (folder, input1))

    # Download the PyADM1 simulation output produced by the pyadm1 step.
    local_in = "dynamic_out.csv"
    faasr_log("Downloading simulation output '%s'" % input1)
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    # Parse the simulation results.
    df = pd.read_csv(local_in)
    if df.shape[0] == 0 or df.shape[1] == 0:
        message = "Simulation output '%s' is empty; nothing to plot." % input1
        faasr_log(message)
        raise ValueError(message)
    faasr_log("Loaded simulation output with %d rows and %d columns"
              % (df.shape[0], df.shape[1]))

    # dynamic_out.csv is written by the model with index=False and no explicit
    # time column, so each row is one dynamic simulation step. Use the row index
    # as the simulation-step axis and plot every output state variable over it.
    columns = list(df.columns)
    steps = range(len(df))

    n = len(columns)
    ncols = 4
    nrows = int(math.ceil(n / float(ncols)))

    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.0 * nrows))
    # Flatten axes to a 1-D list regardless of grid shape.
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for idx, col in enumerate(columns):
        ax = axes[idx]
        # Coerce to numeric so any stray non-numeric cell becomes NaN rather than
        # crashing the plot (never fabricated — just skipped as missing).
        series = pd.to_numeric(df[col], errors="coerce")
        ax.plot(list(steps), series.values, linestyle="-", color="tab:blue")
        ax.set_title(col)
        ax.set_xlabel("simulation step")
        ax.set_ylabel(col)
        ax.grid(True, linestyle=":", alpha=0.5)

    # Hide any unused subplots in the grid.
    for j in range(n, len(axes)):
        axes[j].axis("off")

    fig.suptitle("PyADM1 digester output state variables over simulation time",
                 fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.985))

    local_out = "digester_output_plots.png"
    fig.savefig(local_out, dpi=100)
    plt.close(fig)
    faasr_log("Wrote figure with %d state-variable panels to '%s'" % (n, local_out))

    # Upload the rendered figure.
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded visualization to '%s'" % output1)
