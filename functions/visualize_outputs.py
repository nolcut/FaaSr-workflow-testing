import os
import tempfile

import matplotlib
matplotlib.use('Agg')  # headless — no display server
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def visualize_outputs(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    FaaSr entry point: read ADM1 dynamic simulation results (dynamic_out.csv)
    and produce two multi-panel PNG plots:

      output1 – key substrate and biomass state variables over time
      output2 – effluent / gas-phase output characteristics over time
    """
    faasr_log("visualize_outputs: starting")

    # ------------------------------------------------------------------ #
    # 1.  Download the simulation results from S3
    # ------------------------------------------------------------------ #
    local_csv = "dynamic_out.csv"
    faasr_log(f"visualize_outputs: downloading {input1} from {folder}")
    faasr_get_file(local_file=local_csv, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_csv) or os.path.getsize(local_csv) == 0:
        msg = f"visualize_outputs: input file '{input1}' is missing or empty"
        faasr_log(msg)
        raise RuntimeError(msg)

    # ------------------------------------------------------------------ #
    # 2.  Parse results
    # ------------------------------------------------------------------ #
    faasr_log("visualize_outputs: parsing simulation results")
    df = pd.read_csv(local_csv)

    required_cols = [
        "S_su", "S_aa", "S_fa", "S_ac", "S_pro", "S_bu", "S_va",
        "X_su", "X_aa", "X_fa", "X_c4", "X_pro", "X_ac", "X_h2",
        "pH", "S_gas_h2", "S_gas_ch4", "S_gas_co2", "S_IC", "S_IN",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        msg = f"visualize_outputs: required columns missing from {input1}: {missing}"
        faasr_log(msg)
        raise ValueError(msg)

    # Time axis: row index = simulation day (0 … n-1)
    time = np.arange(len(df), dtype=float)

    # ------------------------------------------------------------------ #
    # 3.  Plot 1 — Substrate and Biomass state variables
    # ------------------------------------------------------------------ #
    faasr_log("visualize_outputs: generating substrate/biomass plot")

    substrate_vars = [
        ("S_su",  r"$S_{su}$ (kg COD m$^{-3}$)",   "monosaccharides"),
        ("S_aa",  r"$S_{aa}$ (kg COD m$^{-3}$)",   "amino acids"),
        ("S_fa",  r"$S_{fa}$ (kg COD m$^{-3}$)",   "LCFA"),
        ("S_ac",  r"$S_{ac}$ (kg COD m$^{-3}$)",   "acetate"),
        ("S_pro", r"$S_{pro}$ (kg COD m$^{-3}$)",  "propionate"),
        ("S_bu",  r"$S_{bu}$ (kg COD m$^{-3}$)",   "butyrate"),
        ("S_va",  r"$S_{va}$ (kg COD m$^{-3}$)",   "valerate"),
    ]
    biomass_vars = [
        ("X_su",  r"$X_{su}$ (kg COD m$^{-3}$)",   "sugar degraders"),
        ("X_aa",  r"$X_{aa}$ (kg COD m$^{-3}$)",   "aa degraders"),
        ("X_fa",  r"$X_{fa}$ (kg COD m$^{-3}$)",   "LCFA degraders"),
        ("X_c4",  r"$X_{c4}$ (kg COD m$^{-3}$)",   "C4 degraders"),
        ("X_pro", r"$X_{pro}$ (kg COD m$^{-3}$)",  "propionate deg."),
        ("X_ac",  r"$X_{ac}$ (kg COD m$^{-3}$)",   "acetate deg."),
        ("X_h2",  r"$X_{h2}$ (kg COD m$^{-3}$)",   "H2 degraders"),
    ]

    # Layout: 4 rows × 4 cols (16 slots) — 7 substrates top, 7 biomass bottom
    ncols = 4
    nrows = 4  # 2 rows substrates + 2 rows biomass
    fig1, axes1 = plt.subplots(nrows, ncols, figsize=(16, 12))
    fig1.suptitle("ADM1 Simulation — Substrate & Biomass State Variables", fontsize=14, fontweight='bold')

    all_vars = substrate_vars + biomass_vars  # 14 variables
    for idx, (col, ylabel, title) in enumerate(all_vars):
        row, col_idx = divmod(idx, ncols)
        ax = axes1[row, col_idx]
        ax.plot(time, df[col].values, linewidth=1.5)
        ax.set_title(title, fontsize=9)
        ax.set_ylabel(ylabel, fontsize=7)
        ax.set_xlabel("Time (days)", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.grid(True, linestyle='--', alpha=0.5)

    # Hide the two unused subplots (slots 14 and 15)
    for unused_idx in range(len(all_vars), nrows * ncols):
        row, col_idx = divmod(unused_idx, ncols)
        axes1[row, col_idx].set_visible(False)

    # Add section labels using text annotations
    fig1.text(0.01, 0.97, "Substrates", fontsize=11, fontweight='bold', color='steelblue', va='top')
    fig1.text(0.01, 0.50, "Biomass", fontsize=11, fontweight='bold', color='darkorange', va='top')

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    local_plot1 = "adm1_substrate_biomass_plot.png"
    fig1.savefig(local_plot1, dpi=150, bbox_inches='tight')
    plt.close(fig1)
    faasr_log(f"visualize_outputs: saved {local_plot1}")

    # ------------------------------------------------------------------ #
    # 4.  Plot 2 — Effluent and gas-flow output characteristics
    # ------------------------------------------------------------------ #
    faasr_log("visualize_outputs: generating effluent/gas-flow plot")

    effluent_vars = [
        ("pH",        "pH",                                            "pH"),
        ("S_gas_h2",  r"$S_{gas,H_2}$ (kg COD m$^{-3}$)",            "gas H2"),
        ("S_gas_ch4", r"$S_{gas,CH_4}$ (kg COD m$^{-3}$)",           "gas CH4"),
        ("S_gas_co2", r"$S_{gas,CO_2}$ (kmol C m$^{-3}$)",           "gas CO2"),
        ("S_IC",      r"$S_{IC}$ (kmol C m$^{-3}$)",                  "inorganic C"),
        ("S_IN",      r"$S_{IN}$ (kmol N m$^{-3}$)",                  "inorganic N"),
    ]

    # Layout: 2 rows × 3 cols
    fig2, axes2 = plt.subplots(2, 3, figsize=(14, 8))
    fig2.suptitle("ADM1 Simulation — Effluent & Gas-Phase Output Characteristics", fontsize=14, fontweight='bold')

    for idx, (col, ylabel, title) in enumerate(effluent_vars):
        row, col_idx = divmod(idx, 3)
        ax = axes2[row, col_idx]
        ax.plot(time, df[col].values, linewidth=1.5, color='darkgreen')
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.set_xlabel("Time (days)", fontsize=8)
        ax.tick_params(labelsize=8)
        ax.grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    local_plot2 = "adm1_effluent_gasflow_plot.png"
    fig2.savefig(local_plot2, dpi=150, bbox_inches='tight')
    plt.close(fig2)
    faasr_log(f"visualize_outputs: saved {local_plot2}")

    # ------------------------------------------------------------------ #
    # 5.  Upload plots to S3
    # ------------------------------------------------------------------ #
    faasr_log(f"visualize_outputs: uploading {output1} to {folder}")
    faasr_put_file(local_file=local_plot1, remote_folder=folder, remote_file=output1)

    faasr_log(f"visualize_outputs: uploading {output2} to {folder}")
    faasr_put_file(local_file=local_plot2, remote_folder=folder, remote_file=output2)

    # ------------------------------------------------------------------ #
    # 6.  Clean up local temp files
    # ------------------------------------------------------------------ #
    for f in (local_csv, local_plot1, local_plot2):
        if os.path.exists(f):
            os.remove(f)

    faasr_log("visualize_outputs: complete")
