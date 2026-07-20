import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Panels to plot: (title, [columns])
PANELS = [
    ("Soluble COD fractions (kgCOD/m³)",
     ["S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac"]),
    ("Dissolved gases & inorganic (kgCOD or kmol/m³)",
     ["S_h2", "S_ch4", "S_IC", "S_IN"]),
    ("Particulate COD fractions (kgCOD/m³)",
     ["X_xc", "X_ch", "X_pr", "X_li"]),
    ("Particulate biomass (kgCOD/m³)",
     ["X_su", "X_aa", "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I"]),
    ("Ion species (kmol/m³)",
     ["S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion", "S_nh3", "S_nh4_ion"]),
    ("Gas-phase concentrations (kgCOD or kmol/m³)",
     ["S_gas_h2", "S_gas_ch4", "S_gas_co2"]),
    ("pH", ["pH"]),
]


def visualize(folder: str, input1: str, output1: str) -> None:
    local_in = "dynamic_out.csv"
    local_out = "simulation_plots.png"

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"visualize: read {input1}")

    df = pd.read_csv(local_in)

    # Use row index as time axis (step number); label x-axis accordingly
    time = np.arange(len(df))

    n_panels = len(PANELS)
    fig, axes = plt.subplots(n_panels, 1, figsize=(14, 3.5 * n_panels), sharex=False)
    fig.suptitle("PyADM1 Simulation Results", fontsize=14, fontweight="bold", y=1.002)

    for ax, (title, cols) in zip(axes, PANELS):
        present = [c for c in cols if c in df.columns]
        if not present:
            ax.set_visible(False)
            continue
        for col in present:
            ax.plot(time, df[col], label=col, linewidth=0.9)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("Time step", fontsize=8)
        ax.legend(fontsize=7, ncol=min(4, len(present)), loc="best")
        ax.grid(True, linewidth=0.4, alpha=0.5)
        ax.tick_params(labelsize=8)

    plt.tight_layout()
    plt.savefig(local_out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    faasr_log(f"visualize: saved figure ({n_panels} panels)")

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize: wrote {output1}")
