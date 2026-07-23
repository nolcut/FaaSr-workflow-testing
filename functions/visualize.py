import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# Step 7: visualize
# Runs once, after all 20 ranked pyadm1 actions have completed (FaaSr fans
# in automatically). Downloads every dynamic_out_<rank>.csv, overlays key
# ADM1 effluent trajectories across the 20 SRT scenarios, and writes
# simulation_plots.png.

FOLDER = "PyADM1-orig"
N_RANKS = 20

# Representative outputs to visualise (name -> axis label).
PLOT_VARS = [
    ("pH", "pH"),
    ("S_ac", "Acetate  S_ac  [kg COD/m3]"),
    ("S_ch4", "Methane  S_ch4  [kg COD/m3]"),
    ("S_IN", "Inorganic N  S_IN  [kmole N/m3]"),
    ("S_gas_ch4", "Gas-phase CH4  S_gas_ch4"),
    ("X_ac", "Acetogens  X_ac  [kg COD/m3]"),
]


def visualize():
    faasr_log("visualize: collecting dynamic_out_*.csv from all ranks")

    runs = {}
    for rank in range(1, N_RANKS + 1):
        name = f"dynamic_out_{rank}.csv"
        try:
            faasr_get_file(
                server_name="S3",
                remote_folder=FOLDER,
                remote_file=name,
                local_folder=".",
                local_file=name,
            )
            runs[rank] = pd.read_csv(name)
        except Exception as exc:  # noqa: BLE001
            faasr_log(f"visualize: could not load {name}: {exc}")

    if not runs:
        faasr_log("visualize: no simulation outputs found; nothing to plot")
        return

    faasr_log(f"visualize: loaded {len(runs)} simulation output files")

    ncols = 2
    nrows = (len(PLOT_VARS) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 4 * nrows))
    axes = axes.flatten()

    cmap = plt.get_cmap("viridis")
    ranks_sorted = sorted(runs.keys())

    for ax, (var, label) in zip(axes, PLOT_VARS):
        for idx, rank in enumerate(ranks_sorted):
            df = runs[rank]
            if var not in df.columns:
                continue
            color = cmap(idx / max(1, len(ranks_sorted) - 1))
            ax.plot(df.index, df[var], color=color, linewidth=0.9,
                    label=f"rank {rank}")
        ax.set_title(label)
        ax.set_xlabel("time step")
        ax.set_ylabel(var)
        ax.grid(True, alpha=0.3)

    # Hide any unused subplots.
    for ax in axes[len(PLOT_VARS):]:
        ax.axis("off")

    # Single shared legend (SRT sweep, low rank = short SRT).
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="lower center", ncol=10,
                   fontsize="small", title="SRT sweep (rank 1..20)")

    fig.suptitle("PyADM1 dynamic simulation across 20 SRT scenarios",
                 fontsize=14)
    fig.tight_layout(rect=[0, 0.06, 1, 0.97])
    fig.savefig("simulation_plots.png", dpi=120)
    plt.close(fig)

    faasr_put_file(
        server_name="S3",
        local_folder=".",
        local_file="simulation_plots.png",
        remote_folder=FOLDER,
        remote_file="simulation_plots.png",
    )
    faasr_log("visualize: wrote simulation_plots.png")
