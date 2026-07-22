def visualize(folder: str, input1: str, output1: str) -> None:
    """Plot the PyADM1 dynamic simulation outputs as a multi-panel PNG figure.

    Reads the dynamic-output time series, detects the time/index column and the
    available variable columns at runtime, and groups them into panels (soluble
    COD, particulate COD, inorganic carbon/nitrogen & ions, gas-phase biogas, and
    pH). Only columns actually present are plotted. Rendered headlessly with the
    Agg backend and written as a PNG.
    """
    import matplotlib
    matplotlib.use("Agg")            # non-interactive, headless backend
    import matplotlib.pyplot as plt
    import pandas as pd

    faasr_log(f"visualize: downloading simulation output '{input1}' from folder '{folder}'")
    local_in = "dynamic_out.csv"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)
    faasr_log(f"visualize: read {len(df)} rows, {len(df.columns)} columns")
    if len(df.columns) == 0 or len(df) == 0:
        msg = "visualize: simulation output CSV is empty"
        faasr_log(msg)
        raise ValueError(msg)

    # --- detect a time/index column at runtime; fall back to the row index ---
    time_candidates = ("time", "Time", "t", "TIME", "index", "Index")
    time_col = next((c for c in time_candidates if c in df.columns), None)
    if time_col is not None:
        x = df[time_col].astype(float).to_numpy()
        x_label = f"{time_col}"
        value_cols = [c for c in df.columns if c != time_col]
    else:
        x = df.index.to_numpy()
        x_label = "time step (row index)"
        value_cols = list(df.columns)
    faasr_log(f"visualize: x-axis = '{x_label}', {len(value_cols)} variable column(s)")

    present = set(value_cols)

    def pick(names):
        """Columns from an explicit ordered list that are present (numeric)."""
        return [c for c in names if c in present and
                pd.api.types.is_numeric_dtype(df[c])]

    def pick_suffix_ion():
        """Any acid/base ion species columns present (name ends with '_ion')."""
        return [c for c in value_cols if c.endswith("_ion") and c in present
                and pd.api.types.is_numeric_dtype(df[c])]

    # --- group available columns into panels (runtime-detected, no hardcoding of
    #     which must exist; empty groups are dropped) ---
    soluble = pick(["S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro",
                    "S_ac", "S_h2", "S_ch4", "S_I"])
    particulate = [c for c in value_cols if c.startswith("X_") and c in present
                   and pd.api.types.is_numeric_dtype(df[c])]
    gas = [c for c in value_cols if c.startswith("S_gas_") and c in present
           and pd.api.types.is_numeric_dtype(df[c])]
    # Inorganic C/N, cation/anion, plus dissolved ion species (exclude gas cols).
    inorganic = pick(["S_IC", "S_IN", "S_cation", "S_anion", "S_nh3", "S_co2",
                      "S_nh4_ion"])
    ion_species = [c for c in pick_suffix_ion()
                   if c not in inorganic and not c.startswith("S_gas_")]
    inorganic_ions = inorganic + [c for c in ion_species if c not in inorganic]
    ph = pick(["pH"])

    panels = [
        ("Soluble COD components (S_*)", soluble, "concentration (kg COD·m$^{-3}$)"),
        ("Particulate COD components (X_*)", particulate, "concentration (kg COD·m$^{-3}$)"),
        ("Inorganic C/N, cations/anions & ion species", inorganic_ions, "concentration (M / kg COD·m$^{-3}$)"),
        ("Gas-phase (biogas) components", gas, "gas-phase concentration"),
        ("pH", ph, "pH"),
    ]
    panels = [(title, cols, ylab) for (title, cols, ylab) in panels if cols]
    if not panels:
        msg = "visualize: no recognizable ADM1 variable columns to plot"
        faasr_log(msg)
        raise ValueError(msg)
    faasr_log("visualize: panels -> " +
              ", ".join(f"{t.split(' (')[0]}[{len(c)}]" for t, c, _ in panels))

    # --- render ---
    n = len(panels)
    fig, axes = plt.subplots(n, 1, figsize=(14, 3.4 * n), squeeze=False)
    axes = axes[:, 0]
    for ax, (title, cols, ylab) in zip(axes, panels):
        for c in cols:
            ax.plot(x, df[c].to_numpy(), label=c, linewidth=1.0)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_ylabel(ylab, fontsize=9)
        ax.set_xlabel(x_label, fontsize=9)
        ax.grid(True, linestyle=":", alpha=0.5)
        # legend outside the axes to avoid covering data; many series possible.
        ncol = 1 if len(cols) <= 8 else 2
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5),
                  fontsize=7, ncol=ncol, frameon=False)
    fig.suptitle("PyADM1 dynamic simulation outputs", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.99))

    local_out = "simulation_plots.png"
    fig.savefig(local_out, dpi=120, bbox_inches="tight")
    plt.close(fig)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize: wrote figure '{output1}' ({n} panel(s)) to folder '{folder}'")
