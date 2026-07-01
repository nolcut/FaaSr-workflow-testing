# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "adm1_model_output.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Required input 'adm1_model_output.csv' (ADM1 model output) not found in S3")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "adm1_results_plot.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output 'adm1_results_plot.png' was not produced in S3")
        raise SystemExit(1)
# --- end contract helpers ---


def visualize_adm1_results(folder: str, input1: str, output1: str) -> None:
    """
    Visualize the ADM1 (BSM2) simulation results produced by run_adm1_model.

    Reads
    -----
    input1 : CSV time-series of ADM1 state variables and derived outputs
             (one row per simulation time step). Produced upstream by
             run_adm1_model as 'adm1_model_output.csv'. Expected columns include
             'time', the 35 ADM1 state variables (S_su, S_aa, ... S_gas_co2) and
             derived quantities: pH, q_gas, p_gas_ch4/co2/h2, P_gas,
             gas_frac_ch4, gas_frac_co2, S_co2, S_nh4_ion, S_H_ion.

    Writes
    ------
    output1 : a single multi-panel PNG figure of the key simulated variables
              (biogas flow rate, biogas composition / methane content, pH,
              VFA concentrations, dissolved COD components and inorganic
              carbon / nitrogen).
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    import os
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    faasr_log("visualize_adm1_results: starting")

    # ------------------------------------------------------------------
    # 1) Download the upstream ADM1 model output CSV from S3
    # ------------------------------------------------------------------
    local_in = "adm1_model_output.csv"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        faasr_log(f"ERROR: input '{input1}' missing or empty after download from S3")
        raise RuntimeError(f"Required input '{input1}' could not be retrieved from S3")

    try:
        df = pd.read_csv(local_in)
    except Exception as e:
        faasr_log(f"ERROR: could not parse '{input1}' as CSV: {e}")
        raise RuntimeError(f"ADM1 model output '{input1}' is not a valid CSV") from e

    if df.empty or df.shape[1] == 0:
        faasr_log(f"ERROR: '{input1}' contains no data rows/columns")
        raise RuntimeError(f"ADM1 model output '{input1}' contains no usable data")

    faasr_log(f"Loaded ADM1 model output: {len(df)} rows, {df.shape[1]} columns")

    # ------------------------------------------------------------------
    # 2) Establish the time axis
    # ------------------------------------------------------------------
    if "time" in df.columns:
        df = df.sort_values("time").reset_index(drop=True)
        t = pd.to_numeric(df["time"], errors="coerce")
        t_label = "Time (d)"
    else:
        faasr_log("WARNING: no 'time' column found; using row index as the time axis")
        t = pd.Series(range(len(df)))
        t_label = "Simulation step"

    def col(name):
        """Return a numeric Series for column `name`, or None if absent/non-numeric."""
        if name not in df.columns:
            return None
        s = pd.to_numeric(df[name], errors="coerce")
        if s.notna().sum() == 0:
            return None
        return s

    # ------------------------------------------------------------------
    # 3) Build the panel definitions from the columns that are actually present
    #    (no fabrication — a panel is only drawn if its source data exists)
    # ------------------------------------------------------------------
    panels = []  # each: (title, ylabel, [(series, label), ...])

    # Biogas flow rate
    q_gas = col("q_gas")
    if q_gas is not None:
        panels.append((
            "Biogas Flow Rate",
            "q_gas (m$^3$/d)",
            [(q_gas, "Biogas flow")],
        ))

    # Biogas composition (methane / carbon-dioxide content)
    comp_series = []
    frac_ch4 = col("gas_frac_ch4")
    frac_co2 = col("gas_frac_co2")
    if frac_ch4 is not None:
        comp_series.append((frac_ch4 * 100.0, "CH$_4$"))
    if frac_co2 is not None:
        comp_series.append((frac_co2 * 100.0, "CO$_2$"))
    if comp_series:
        panels.append((
            "Biogas Composition (Methane Content)",
            "Gas fraction (% v/v)",
            comp_series,
        ))
    else:
        # fall back to partial pressures if volume fractions are unavailable
        pp_series = []
        for cname, lbl in (("p_gas_ch4", "CH$_4$"), ("p_gas_co2", "CO$_2$"),
                           ("p_gas_h2", "H$_2$")):
            s = col(cname)
            if s is not None:
                pp_series.append((s, lbl))
        if pp_series:
            panels.append((
                "Biogas Partial Pressures",
                "Partial pressure (bar)",
                pp_series,
            ))

    # pH
    pH = col("pH")
    if pH is not None:
        panels.append((
            "Reactor pH",
            "pH",
            [(pH, "pH")],
        ))

    # Volatile fatty acids (VFA) concentrations
    vfa_series = []
    for cname, lbl in (("S_va", "Valerate (S_va)"), ("S_bu", "Butyrate (S_bu)"),
                       ("S_pro", "Propionate (S_pro)"), ("S_ac", "Acetate (S_ac)")):
        s = col(cname)
        if s is not None:
            vfa_series.append((s, lbl))
    if vfa_series:
        panels.append((
            "Volatile Fatty Acid Concentrations",
            "Concentration (kg COD/m$^3$)",
            vfa_series,
        ))

    # Dissolved COD components (soluble organic COD carriers)
    cod_components = ["S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro",
                      "S_ac", "S_h2", "S_ch4", "S_I"]
    present_cod = [c for c in cod_components if col(c) is not None]
    if present_cod:
        cod_total = None
        for c in present_cod:
            s = col(c)
            cod_total = s if cod_total is None else (cod_total + s)
        cod_series = [(cod_total, "Total soluble COD")]
        # also show dissolved methane individually if available
        s_ch4 = col("S_ch4")
        if s_ch4 is not None:
            cod_series.append((s_ch4, "Dissolved CH$_4$ (S_ch4)"))
        panels.append((
            "Soluble COD",
            "COD (kg COD/m$^3$)",
            cod_series,
        ))

    # Inorganic carbon and nitrogen
    inorg_series = []
    s_ic = col("S_IC")
    s_in = col("S_IN")
    if s_ic is not None:
        inorg_series.append((s_ic, "Inorganic carbon (S_IC)"))
    if s_in is not None:
        inorg_series.append((s_in, "Inorganic nitrogen (S_IN)"))
    if inorg_series:
        panels.append((
            "Inorganic Carbon & Nitrogen",
            "Concentration (kmole/m$^3$)",
            inorg_series,
        ))

    if not panels:
        faasr_log("ERROR: none of the expected ADM1 result variables "
                  "(q_gas, gas fractions, pH, VFAs, COD components, S_IC/S_IN) "
                  f"were found in '{input1}'. Columns present: {list(df.columns)}")
        raise RuntimeError(
            f"ADM1 model output '{input1}' does not contain any recognizable "
            "ADM1 result columns to visualize"
        )

    faasr_log(f"Rendering {len(panels)} result panels")

    # ------------------------------------------------------------------
    # 4) Render the multi-panel figure
    # ------------------------------------------------------------------
    n = len(panels)
    ncols = 2 if n > 1 else 1
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(7.0 * ncols, 3.6 * nrows),
                             squeeze=False)
    flat_axes = [ax for row in axes for ax in row]

    colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf"]

    for ax, (title, ylabel, series_list) in zip(flat_axes, panels):
        for i, (series, lbl) in enumerate(series_list):
            ax.plot(t, series, linewidth=1.8, label=lbl,
                    color=colors[i % len(colors)])
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel(t_label, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.5)
        if len(series_list) > 1:
            ax.legend(fontsize=8)

    # hide any unused axes
    for ax in flat_axes[n:]:
        ax.axis("off")

    fig.suptitle("ADM1 (BSM2) Simulation Results", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    local_out = "adm1_results_plot.png"
    fig.savefig(local_out, dpi=150, bbox_inches="tight")
    plt.close(fig)

    if not os.path.exists(local_out) or os.path.getsize(local_out) == 0:
        faasr_log("ERROR: result plot PNG was not written or is empty")
        raise RuntimeError("Failed to produce adm1_results_plot.png")

    # ------------------------------------------------------------------
    # 5) Upload the figure to S3
    # ------------------------------------------------------------------
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded ADM1 results plot to S3 as '{output1}'")
    faasr_log("visualize_adm1_results: completed successfully")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---