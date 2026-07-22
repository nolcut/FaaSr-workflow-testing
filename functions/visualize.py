def visualize(folder: str, input1: str, output1: str) -> None:
    """Plot the PyADM1 dynamic simulation outputs as a multi-panel PNG figure.

    Fan-in sink for the 20 ranked pyadm1 instances: discovers every per-rank
    output (dynamic_out_{rank}.csv) in the folder, reads them all, and renders a
    multi-panel figure comparing the key state variables across the SRT runs
    (one line per SRT scenario per panel) so the effect of varied SRT is visible.
    If only a single output file exists, it is plotted as before (variables grouped
    into per-category panels). Rendered headlessly with the Agg backend as a PNG.
    """
    import re
    import matplotlib
    matplotlib.use("Agg")            # non-interactive, headless backend
    import matplotlib.pyplot as plt
    import pandas as pd

    # --- discover ALL ranked outputs (fan-in from the ranked pyadm1 predecessor) ---
    # Build a matcher from the {rank} template, e.g. "dynamic_out_{rank}.csv".
    template = input1
    rank_re = re.compile("^" + re.escape(template).replace(r"\{rank\}", r"(\d+)") + "$")

    faasr_log(f"visualize: discovering ranked outputs matching '{template}' in folder '{folder}'")
    keys = faasr_get_folder_list(prefix=folder)
    matched = []
    for key in keys:
        base = key.rsplit("/", 1)[-1]
        m = rank_re.match(base)
        if m:
            matched.append((int(m.group(1)), base))
    matched.sort(key=lambda t: t[0])

    if not matched:
        # No {rank} placeholder (or nothing matched) -> treat input1 as a literal name.
        if "{rank}" not in template:
            matched = [(None, template)]
        else:
            msg = f"visualize: no files matching '{template}' found in folder '{folder}'"
            faasr_log(msg)
            raise FileNotFoundError(msg)

    faasr_log(f"visualize: found {len(matched)} simulation output file(s): "
              + ", ".join(b for _, b in matched))

    # --- download and read each output ---
    runs = []  # list of (rank, DataFrame)
    for rank, base in matched:
        local_in = f"dynamic_out_rank_{rank}.csv" if rank is not None else "dynamic_out.csv"
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)
        df = pd.read_csv(local_in)
        if len(df.columns) == 0 or len(df) == 0:
            msg = f"visualize: simulation output '{base}' is empty"
            faasr_log(msg)
            raise ValueError(msg)
        runs.append((rank, df))
        faasr_log(f"visualize: read '{base}' -> {len(df)} rows, {len(df.columns)} columns")

    def detect_x(df):
        """Detect a time/index column; fall back to the row index."""
        time_candidates = ("time", "Time", "t", "TIME", "index", "Index")
        time_col = next((c for c in time_candidates if c in df.columns), None)
        if time_col is not None:
            return df[time_col].astype(float).to_numpy(), f"{time_col}", \
                [c for c in df.columns if c != time_col]
        return df.index.to_numpy(), "time step (row index)", list(df.columns)

    local_out = "simulation_plots.png"

    if len(runs) == 1:
        # ---------- single-output case: plot as before (grouped panels) ----------
        _, df = runs[0]
        x, x_label, value_cols = detect_x(df)
        faasr_log(f"visualize: single output; x-axis = '{x_label}', {len(value_cols)} variable column(s)")
        present = set(value_cols)

        def pick(names):
            return [c for c in names if c in present and pd.api.types.is_numeric_dtype(df[c])]

        soluble = pick(["S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro",
                        "S_ac", "S_h2", "S_ch4", "S_I"])
        particulate = [c for c in value_cols if c.startswith("X_") and c in present
                       and pd.api.types.is_numeric_dtype(df[c])]
        gas = [c for c in value_cols if c.startswith("S_gas_") and c in present
               and pd.api.types.is_numeric_dtype(df[c])]
        inorganic = pick(["S_IC", "S_IN", "S_cation", "S_anion", "S_nh3", "S_co2", "S_nh4_ion"])
        ion_species = [c for c in value_cols if c.endswith("_ion") and c in present
                       and pd.api.types.is_numeric_dtype(df[c])
                       and c not in inorganic and not c.startswith("S_gas_")]
        inorganic_ions = inorganic + [c for c in ion_species if c not in inorganic]
        ph = pick(["pH"])

        panels = [
            ("Soluble COD components (S_*)", soluble, "concentration (kg COD·m$^{-3}$)"),
            ("Particulate COD components (X_*)", particulate, "concentration (kg COD·m$^{-3}$)"),
            ("Inorganic C/N, cations/anions & ion species", inorganic_ions, "concentration (M / kg COD·m$^{-3}$)"),
            ("Gas-phase (biogas) components", gas, "gas-phase concentration"),
            ("pH", ph, "pH"),
        ]
        panels = [(t, c, y) for (t, c, y) in panels if c]
        if not panels:
            msg = "visualize: no recognizable ADM1 variable columns to plot"
            faasr_log(msg)
            raise ValueError(msg)
        faasr_log("visualize: panels -> " +
                  ", ".join(f"{t.split(' (')[0]}[{len(c)}]" for t, c, _ in panels))

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
            ncol = 1 if len(cols) <= 8 else 2
            ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5),
                      fontsize=7, ncol=ncol, frameon=False)
        fig.suptitle("PyADM1 dynamic simulation outputs", fontsize=14, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.99))
        fig.savefig(local_out, dpi=120, bbox_inches="tight")
        plt.close(fig)
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
        faasr_log(f"visualize: wrote figure '{output1}' ({n} panel(s)) to folder '{folder}'")
        return

    # ---------- multi-output case: overlay key variables across SRT runs ----------
    # Detect axis/columns from the first run (all runs share the ADM1 schema).
    _, df0 = runs[0]
    _, x_label, value_cols0 = detect_x(df0)
    present0 = set(value_cols0)

    # Curated, ordered set of key state variables whose SRT sensitivity matters most;
    # keep only those actually present and numeric (runtime detection preserved).
    key_pref = ["pH", "S_ac", "S_ch4", "S_gas_ch4", "S_pro", "S_va", "S_bu",
                "S_IN", "S_IC", "S_gas_co2", "S_gas_h2", "S_h2"]
    key_vars = [c for c in key_pref
                if c in present0 and pd.api.types.is_numeric_dtype(df0[c])]
    if not key_vars:
        # Fall back to the first several numeric variable columns present.
        key_vars = [c for c in value_cols0
                    if pd.api.types.is_numeric_dtype(df0[c])][:9]
    if not key_vars:
        msg = "visualize: no recognizable ADM1 variable columns to plot"
        faasr_log(msg)
        raise ValueError(msg)
    faasr_log(f"visualize: comparing {len(key_vars)} key variable(s) across "
              f"{len(runs)} SRT runs -> {', '.join(key_vars)}")

    cmap = plt.get_cmap("viridis")
    n_runs = len(runs)

    def color_for(i):
        return cmap(i / max(1, n_runs - 1))

    n = len(key_vars)
    fig, axes = plt.subplots(n, 1, figsize=(14, 3.2 * n), squeeze=False)
    axes = axes[:, 0]
    for ax, var in zip(axes, key_vars):
        for i, (rank, df) in enumerate(runs):
            if var not in df.columns or not pd.api.types.is_numeric_dtype(df[var]):
                continue
            x, _, _ = detect_x(df)
            ax.plot(x, df[var].to_numpy(), label=f"SRT run {rank}",
                    color=color_for(i), linewidth=1.0)
        ax.set_title(f"{var} across SRT runs", fontsize=11, fontweight="bold")
        ax.set_ylabel(var, fontsize=9)
        ax.set_xlabel(x_label, fontsize=9)
        ax.grid(True, linestyle=":", alpha=0.5)
        ncol = 1 if n_runs <= 10 else 2
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5),
                  fontsize=6, ncol=ncol, frameon=False, title="scenario")
    fig.suptitle(f"PyADM1 dynamic outputs across {n_runs} varied-SRT runs",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.99))
    fig.savefig(local_out, dpi=120, bbox_inches="tight")
    plt.close(fig)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize: wrote comparison figure '{output1}' "
              f"({n} panel(s), {n_runs} runs) to folder '{folder}'")
