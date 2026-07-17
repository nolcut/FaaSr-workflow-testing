def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    import matplotlib
    matplotlib.use("Agg")  # headless / non-interactive backend (no display)
    import matplotlib.pyplot as plt
    import pandas as pd

    local_in = "dynamic_out.csv"
    local_out = "simulation_plots.png"

    faasr_log(f"visualize_outputs: fetching {input1} from folder {folder}")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)
    if df.empty:
        msg = f"visualize_outputs: {input1} contains no rows to plot"
        faasr_log(msg)
        raise ValueError(msg)

    # The PyADM1 dynamic output is a per-time-step table of state variables with
    # no explicit time column, so use the simulation step index as the x-axis.
    x = range(len(df))
    xlabel = "Simulation step"

    # Groups of key simulated state variables to visualise over time.
    panels = [
        ("Volatile fatty acids (kg COD/m3)",
         ["S_va", "S_bu", "S_pro", "S_ac"]),
        ("Inorganic carbon & nitrogen (kmole/m3)",
         ["S_IC", "S_IN"]),
        ("Gas-phase components",
         ["S_gas_h2", "S_gas_ch4", "S_gas_co2"]),
        ("pH",
         ["pH"]),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    axes = axes.flatten()

    plotted_any = False
    for ax, (title, cols) in zip(axes, panels):
        present = [c for c in cols if c in df.columns]
        for c in present:
            ax.plot(x, df[c], label=c)
            plotted_any = True
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Concentration" if title != "pH" else "pH")
        if present:
            ax.legend(loc="best", fontsize=8)
        else:
            ax.text(0.5, 0.5, "no data", ha="center", va="center",
                    transform=ax.transAxes)

    if not plotted_any:
        msg = (
            f"visualize_outputs: none of the expected state-variable columns were "
            f"found in {input1}; columns present: {list(df.columns)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    fig.suptitle("PyADM1 Digester Simulation Outputs", fontsize=16)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(local_out, dpi=120)
    plt.close(fig)
    faasr_log(f"visualize_outputs: saved figure with {len(df)} time steps")

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_outputs: wrote {output1} to folder {folder}")
