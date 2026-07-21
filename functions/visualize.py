"""FaaSr step 7: visualize.

Plot the PyADM1 simulation outputs (dynamic_out.csv) and write
simulation_plots.png. A grid of subplots covers the most informative digester
state variables; any that are absent are simply skipped.
"""

try:
    from FaaSr_py.client.py_client_stubs import faasr_get_file, faasr_put_file, faasr_log
except Exception:  # pragma: no cover
    pass

import matplotlib
matplotlib.use("Agg")  # headless backend
import matplotlib.pyplot as plt
import pandas as pd

# (column, human-readable title) pairs to plot, in order.
PLOT_VARS = [
    ("pH", "pH"),
    ("S_ac", "Acetate S_ac (kg COD/m3)"),
    ("S_ch4", "Dissolved methane S_ch4 (kg COD/m3)"),
    ("S_IN", "Inorganic nitrogen S_IN (kmole N/m3)"),
    ("S_IC", "Inorganic carbon S_IC (kmole C/m3)"),
    ("S_gas_ch4", "Gas-phase methane S_gas_ch4"),
    ("S_gas_co2", "Gas-phase CO2 S_gas_co2"),
    ("S_gas_h2", "Gas-phase hydrogen S_gas_h2"),
    ("S_va", "Valerate S_va (kg COD/m3)"),
]


def visualize(folder, input_file="dynamic_out.csv",
              output_file="simulation_plots.png"):
    faasr_log(f"visualize: downloading {folder}/{input_file}")
    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file="dynamic_out.csv")

    df = pd.read_csv("dynamic_out.csv")

    # x-axis: use 'time' if present, else the row index.
    if "time" in df.columns:
        x = df["time"].to_numpy()
        xlabel = "time (d)"
    else:
        x = range(len(df))
        xlabel = "step"

    available = [(c, t) for c, t in PLOT_VARS if c in df.columns]
    if not available:
        # Fall back to the first few numeric columns.
        numeric = df.select_dtypes("number").columns.tolist()
        available = [(c, c) for c in numeric[:9]]
    faasr_log(f"visualize: plotting {len(available)} variables")

    ncols = 3
    nrows = (len(available) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 4 * nrows), squeeze=False)

    for idx, (col, title) in enumerate(available):
        ax = axes[idx // ncols][idx % ncols]
        ax.plot(x, df[col].to_numpy(), color="tab:blue")
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.grid(True, alpha=0.3)

    # Hide any unused subplot axes.
    for idx in range(len(available), nrows * ncols):
        axes[idx // ncols][idx % ncols].axis("off")

    fig.suptitle("PyADM1 dynamic simulation outputs", fontsize=16)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(output_file, dpi=120)
    plt.close(fig)

    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"visualize: wrote {folder}/{output_file}")
