# Step 7: visualize
# Runs once after all 20 ranked PyADM1 simulations complete. Downloads every
# dynamic_out_<rank>.csv, overlays a set of key ADM1 outputs (one subplot per
# variable, one line per SRT run) and writes simulation_plots.png.

# Representative outputs to plot (fall back gracefully if a column is absent).
PLOT_VARS = ["pH", "S_ac", "S_ch4", "S_IN", "S_IC", "X_ac"]


def visualize_outputs(folder, output_prefix="dynamic_out",
                      plot_file="simulation_plots.png"):
    import os
    import re
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # discover all simulation outputs for this workflow
    listing = faasr_get_folder_list(server_name="S3", prefix=folder)
    names = [os.path.basename(str(x)) for x in listing]
    pattern = re.compile(rf"^{re.escape(output_prefix)}_(\d+)\.csv$")
    runs = sorted(
        [(int(m.group(1)), n) for n in names for m in [pattern.match(n)] if m],
        key=lambda p: p[0],
    )
    if not runs:
        faasr_log("visualize_outputs: no dynamic_out_*.csv files found")
        return

    faasr_log(f"visualize_outputs: found {len(runs)} simulation output(s)")

    frames = []
    for rank, fname in runs:
        faasr_get_file(remote_folder=folder, remote_file=fname,
                       local_folder=".", local_file=fname)
        frames.append((rank, pd.read_csv(fname)))

    # only plot variables that actually exist in the outputs
    available = [v for v in PLOT_VARS if v in frames[0][1].columns]
    if not available:
        available = list(frames[0][1].columns[:6])

    ncols = 2
    nrows = (len(available) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4 * nrows), squeeze=False)

    for idx, var in enumerate(available):
        ax = axes[idx // ncols][idx % ncols]
        for rank, df in frames:
            if var in df.columns:
                ax.plot(range(len(df)), df[var], linewidth=0.9,
                        label=f"run {rank}")
        ax.set_title(var)
        ax.set_xlabel("time step")
        ax.set_ylabel(var)
        ax.grid(True, alpha=0.3)
    # hide any unused axes
    for j in range(len(available), nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")

    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=min(len(runs), 10),
               fontsize="small")
    fig.suptitle("PyADM1 dynamic simulation outputs across SRT variants", y=1.0)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(plot_file, dpi=120, bbox_inches="tight")
    plt.close(fig)

    faasr_put_file(local_folder=".", local_file=plot_file,
                   remote_folder=folder, remote_file=plot_file)
    faasr_log(f"visualize_outputs: wrote {folder}/{plot_file}")
