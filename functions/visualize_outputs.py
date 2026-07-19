def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    """Visualize the PyADM1 dynamic-simulation output as time-series plots.

    Reads the simulation output CSV (input1) from the S3 folder, plots every
    numeric state/output variable against time (a 'time' column if present,
    otherwise the simulation step index) as a grid of line subplots, and uploads
    the resulting figure as a PNG (output1). Uses a headless matplotlib backend
    (Agg) so it runs with no display server. Plotted columns are derived from the
    data at runtime.
    """
    import os
    import matplotlib
    matplotlib.use("Agg")  # headless backend, no display server
    import matplotlib.pyplot as plt
    import pandas as pd

    local_in = "dynamic_out.csv"
    local_out = "simulation_plots.png"

    faasr_log(f"visualize_outputs: fetching {input1} from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)
    if df.shape[0] == 0:
        msg = f"visualize_outputs: input {input1} contains no rows to plot"
        faasr_log(msg)
        raise ValueError(msg)

    # Derive the time axis and the columns to plot at runtime.
    if "time" in df.columns:
        x = df["time"]
        x_label = "time (d)"
        plot_cols = [c for c in df.columns if c != "time"]
    else:
        x = df.index
        x_label = "simulation step"
        plot_cols = list(df.columns)

    # Keep only numeric columns (the state/output variables).
    plot_cols = [c for c in plot_cols
                 if pd.api.types.is_numeric_dtype(df[c])]
    if not plot_cols:
        msg = (f"visualize_outputs: no numeric columns to plot in {input1}; "
               f"columns are {list(df.columns)}")
        faasr_log(msg)
        raise ValueError(msg)

    n = len(plot_cols)
    ncols = 4
    nrows = (n + ncols - 1) // ncols
    faasr_log(f"visualize_outputs: plotting {n} variables over {len(df)} steps "
              f"in a {nrows}x{ncols} grid")

    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 2.6 * nrows),
                             squeeze=False)
    flat = axes.flatten()
    for ax, col in zip(flat, plot_cols):
        ax.plot(x, df[col], linewidth=0.9)
        ax.set_title(col, fontsize=9)
        ax.set_xlabel(x_label, fontsize=7)
        ax.tick_params(labelsize=6)
    # hide any unused subplot axes
    for ax in flat[n:]:
        ax.axis("off")

    fig.suptitle("PyADM1 dynamic simulation outputs", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(local_out, dpi=120)
    plt.close(fig)

    faasr_log(f"visualize_outputs: uploading figure to {output1}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    for f in (local_in, local_out):
        if os.path.exists(f):
            os.remove(f)

    faasr_log("visualize_outputs: complete")
