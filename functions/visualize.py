import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def visualize(folder, input_prefix, count=20, output_file="simulation_plots.png"):
    """Step 7 - overlay the PyADM1 outputs from all ranked SRT scenarios and
    write simulation_plots.png.

    Runs once (after every ranked pyadm1 invocation has completed, thanks to
    FaaSr's rank synchronization).  Downloads dynamic_out_1..count.csv and plots
    a few representative state variables, one coloured line per SRT scenario.
    """
    runs = []
    for i in range(1, int(count) + 1):
        fname = "{}_{}.csv".format(input_prefix, i)
        try:
            faasr_get_file(server_name="S3", remote_folder=folder,
                           remote_file=fname, local_file=fname)
            runs.append((i, pd.read_csv(fname)))
        except Exception as exc:  # noqa: BLE001
            faasr_log("visualize: could not load {}: {}".format(fname, exc))

    if not runs:
        faasr_log("visualize: no simulation outputs found; nothing to plot")
        return

    # Representative digester outputs: acetate, methane, pH, inorganic nitrogen.
    variables = ["S_ac", "S_ch4", "pH", "S_IN"]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.ravel()
    cmap = plt.get_cmap("viridis")
    denom = max(1, len(runs) - 1)

    for ax, var in zip(axes, variables):
        plotted = False
        for j, (i, df) in enumerate(runs):
            if var in df.columns:
                ax.plot(np.arange(len(df)), df[var],
                        color=cmap(j / denom), linewidth=1.0)
                plotted = True
        ax.set_title(var)
        ax.set_xlabel("time step")
        ax.set_ylabel(var)
        if not plotted:
            ax.text(0.5, 0.5, "column '{}' not found".format(var),
                    ha="center", va="center", transform=ax.transAxes)

    sm = plt.cm.ScalarMappable(cmap=cmap,
                               norm=plt.Normalize(vmin=1, vmax=len(runs)))
    fig.colorbar(sm, ax=axes.tolist(), label="SRT scenario (rank)")
    fig.suptitle("PyADM1 dynamic outputs across {} SRT scenarios".format(len(runs)))

    fig.savefig(output_file, dpi=120, bbox_inches="tight")
    faasr_put_file(server_name="S3", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log("visualize: plotted {} runs; wrote {}/{}".format(
        len(runs), folder, output_file))
