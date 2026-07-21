import matplotlib
matplotlib.use("Agg")  # headless backend for FaaS runners
import matplotlib.pyplot as plt
import pandas as pd

# Representative ADM1 outputs to plot (skipped automatically if absent).
PLOT_COLUMNS = [
    ("pH", "pH"),
    ("S_ac", "Acetate S_ac (kgCOD/m3)"),
    ("S_ch4", "Methane S_ch4 (kgCOD/m3)"),
    ("S_IN", "Inorganic N S_IN (kmole N/m3)"),
    ("S_gas_ch4", "Gas-phase methane S_gas_ch4"),
    ("S_gas_h2", "Gas-phase hydrogen S_gas_h2"),
]


def visualize_results(folder="PyADM1-orig",
                      input_file="dynamic_out.csv",
                      output_file="simulation_plots.png"):
    """Step 7 - plot the PyADM1 simulation outputs and write simulation_plots.png."""
    faasr_get_file(remote_folder=folder, remote_file=input_file, local_file="dynamic_out.csv")
    df = pd.read_csv("dynamic_out.csv")

    # Build an x-axis: use 'time' if present, otherwise the row index (step number).
    if "time" in df.columns:
        x = pd.to_numeric(df["time"], errors="coerce")
        xlabel = "time (d)"
    else:
        x = range(len(df))
        xlabel = "simulation step"

    cols = [(c, lbl) for c, lbl in PLOT_COLUMNS if c in df.columns]
    if not cols:
        cols = [(c, c) for c in df.columns[:6]]

    n = len(cols)
    ncols = 2
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.2 * nrows), squeeze=False)

    for i, (col, label) in enumerate(cols):
        ax = axes[i // ncols][i % ncols]
        ax.plot(x, df[col], color="tab:blue")
        ax.set_title(label)
        ax.set_xlabel(xlabel)
        ax.grid(True, alpha=0.3)

    # Hide any unused subplot axes.
    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")

    fig.suptitle("PyADM1 dynamic simulation outputs", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig("simulation_plots.png", dpi=150)
    plt.close(fig)

    faasr_put_file(local_file="simulation_plots.png", remote_folder=folder, remote_file=output_file)
    faasr_log(f"visualize_results: wrote {len(cols)} panels to {folder}/{output_file}")
