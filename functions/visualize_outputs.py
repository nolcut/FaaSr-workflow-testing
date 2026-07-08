import matplotlib
matplotlib.use("Agg")  # headless backend for FaaSr runners

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def visualize_outputs(output_folder="pyadm1-outputs",
                      validated_folder="pyadm1-validated",
                      output_file="dynamic_out.csv",
                      influent_file="digester_influent.csv",
                      plot_file="pyadm1_results.png"):
    """
    FaaSr stage 3 of 3.

    Downloads the PyADM1 dynamic output (dynamic_out.csv) from S3 and renders a
    multi-panel summary figure of the anaerobic-digestion dynamics: pH,
    volatile fatty acids, gas-phase components, methane/inorganic carbon and
    the biomass populations. The PNG is uploaded back to S3.
    """

    faasr_get_file(remote_folder=output_folder, remote_file=output_file,
                   local_folder=".", local_file=output_file)
    df = pd.read_csv(output_file)
    faasr_log(f"visualize_outputs: loaded {output_file} "
              f"({len(df)} rows, {len(df.columns)} columns).")

    # Use the influent time vector for the x-axis when it lines up; otherwise
    # fall back to the simulation step index.
    x = np.arange(len(df))
    xlabel = "Simulation step"
    try:
        faasr_get_file(remote_folder=validated_folder,
                       remote_file=influent_file,
                       local_folder=".", local_file=influent_file)
        t = pd.read_csv(influent_file)["time"].to_numpy()
        if len(t) == len(df):
            x = t
            xlabel = "Time (days)"
    except Exception as e:  # noqa: BLE001 - time axis is best-effort
        faasr_log(f"visualize_outputs: using step index for x-axis ({e}).")

    # A brand-neutral, colour-blind-safe categorical palette.
    palette = ["#4C78A8", "#F58518", "#54A24B", "#E45756",
               "#72B7B2", "#B279A2", "#EECA3B", "#9D755D"]

    def _plot(ax, cols, title, ylabel):
        present = [c for c in cols if c in df.columns]
        for i, c in enumerate(present):
            ax.plot(x, df[c], label=c, color=palette[i % len(palette)],
                    linewidth=1.6)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(True, alpha=0.25, linewidth=0.6)
        if present:
            ax.legend(fontsize=7, ncol=2, frameon=False)

    fig, axes = plt.subplots(2, 3, figsize=(18, 9))
    fig.suptitle("PyADM1 Anaerobic Digestion — Dynamic Simulation Results",
                 fontsize=15, fontweight="bold")

    _plot(axes[0, 0], ["pH"], "Reactor pH", "pH")
    _plot(axes[0, 1],
          ["S_va", "S_bu", "S_pro", "S_ac"],
          "Volatile fatty acids", "kg COD / m^3")
    _plot(axes[0, 2],
          ["S_gas_h2", "S_gas_ch4", "S_gas_co2"],
          "Gas-phase components", "concentration")
    _plot(axes[1, 0],
          ["S_ch4", "S_IC", "S_IN"],
          "Methane & inorganic C/N", "conc. (kgCOD or kmole /m^3)")
    _plot(axes[1, 1],
          ["S_su", "S_aa", "S_fa"],
          "Soluble substrates", "kg COD / m^3")
    _plot(axes[1, 2],
          ["X_su", "X_aa", "X_fa", "X_c4", "X_pro", "X_ac", "X_h2"],
          "Biomass populations", "kg COD / m^3")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(plot_file, dpi=150)
    plt.close(fig)

    faasr_put_file(local_folder=".", local_file=plot_file,
                   remote_folder=output_folder, remote_file=plot_file)
    faasr_log(f"visualize_outputs: figure written and uploaded as "
              f"'{output_folder}/{plot_file}'.")
