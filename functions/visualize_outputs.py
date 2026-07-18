def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    """Final (sink) step of the PyADM1 digester workflow.

    Reads the PyADM1 dynamic simulation output (input1, a CSV of time-series
    state variables and gas flows), renders line plots of the key output
    variables versus time using a headless matplotlib backend, and uploads the
    resulting PNG figure as output1.

    The columns to plot are derived from the actual output data at runtime
    (grouped by ADM1 naming conventions), not a hardcoded schema.
    """
    import matplotlib
    matplotlib.use("Agg")  # headless / non-interactive backend
    import matplotlib.pyplot as plt
    import pandas as pd

    local_in = "dynamic_out.csv"
    local_out = "simulation_plots.png"

    faasr_log(f"visualize_outputs: fetching '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)
    if df.shape[0] == 0 or df.shape[1] == 0:
        msg = f"visualize_outputs: '{input1}' is empty — nothing to plot"
        faasr_log(msg)
        raise ValueError(msg)

    # --- Determine the time / x-axis ---------------------------------------
    # dynamic_out.csv has no explicit 'time' column, so fall back to the row
    # index (one row per simulation time step). If a time-like column is
    # present in some other output variant, use it and exclude it from plots.
    time_col = None
    for cand in ("time", "Time", "t"):
        if cand in df.columns:
            time_col = cand
            break
    if time_col is not None:
        x = df[time_col].to_numpy()
        x_label = f"{time_col} (d)"
        plot_candidates = [c for c in df.columns if c != time_col]
    else:
        x = range(len(df))
        x_label = "simulation time step"
        plot_candidates = list(df.columns)

    # keep only numeric columns
    numeric_cols = [c for c in plot_candidates
                    if pd.api.types.is_numeric_dtype(df[c])]

    # --- Group key output variables by ADM1 naming conventions -------------
    def present(cols):
        return [c for c in cols if c in numeric_cols]

    groups = []
    grp_ph = present(["pH"])
    if grp_ph:
        groups.append(("pH", grp_ph))

    grp_gas = present([c for c in numeric_cols if c.startswith("S_gas")])
    if grp_gas:
        groups.append(("Gas-phase components (S_gas_*)", grp_gas))

    grp_ch4 = present(["S_ch4", "S_h2"])
    if grp_ch4:
        groups.append(("Dissolved methane & hydrogen", grp_ch4))

    grp_vfa = present(["S_va", "S_bu", "S_pro", "S_ac"])
    if grp_vfa:
        groups.append(("Volatile fatty acids", grp_vfa))

    grp_inorg = present(["S_IC", "S_IN"])
    if grp_inorg:
        groups.append(("Inorganic carbon & nitrogen", grp_inorg))

    # Fallback / completeness: if the curated groups covered nothing, plot
    # every numeric column so we never emit an empty figure.
    if not groups:
        groups = [(c, [c]) for c in numeric_cols]

    faasr_log(
        f"visualize_outputs: {len(df)} time steps, {len(numeric_cols)} numeric "
        f"columns, {len(groups)} plot panel(s)"
    )

    # --- Build the figure --------------------------------------------------
    n_panels = len(groups)
    ncols = 1 if n_panels == 1 else 2
    nrows = (n_panels + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(7 * ncols, 3.2 * nrows),
                             squeeze=False)
    flat_axes = [ax for row in axes for ax in row]

    for ax, (title, cols) in zip(flat_axes, groups):
        for c in cols:
            ax.plot(x, df[c].to_numpy(), label=c, linewidth=1.0)
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel("value")
        ax.legend(loc="best", fontsize="small")
        ax.grid(True, alpha=0.3)

    # hide any unused axes
    for ax in flat_axes[n_panels:]:
        ax.axis("off")

    fig.suptitle("PyADM1 digester simulation outputs", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(local_out, dpi=120)
    plt.close(fig)

    faasr_log(f"visualize_outputs: uploading figure as '{output1}'")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log("visualize_outputs: visualization complete")
