import os
import matplotlib
matplotlib.use("Agg")  # headless backend for FaaSr runners
import matplotlib.pyplot as plt
import pandas as pd


def visualize_outputs(folder, output_file, influent_file, plot_file):
    """
    FaaSr function: visualize the PyADM1 simulation outputs.

    Downloads the simulation result (dynamic_out.csv) from S3, and, when
    available, the influent file to use its `time` column as the x-axis.
    Produces a multi-panel figure summarising the key digester dynamics
    (volatile fatty acids, pH, gas-phase concentrations, and dissolved
    gases/inorganics) and uploads it to S3 as `plot_file`.
    """

    # --- Download simulation output -----------------------------------------
    faasr_get_file(remote_folder=folder, remote_file=output_file,
                   local_folder=".", local_file="dynamic_out.csv")
    results = pd.read_csv("dynamic_out.csv")

    # --- Build an x-axis (prefer real simulation time) ----------------------
    x = range(len(results))
    xlabel = "Simulation step"
    try:
        faasr_get_file(remote_folder=folder, remote_file=influent_file,
                       local_folder=".", local_file="digester_influent.csv")
        influent = pd.read_csv("digester_influent.csv")
        if "time" in influent.columns and len(influent) == len(results):
            x = influent["time"].values
            xlabel = "Time (d)"
    except Exception as e:
        faasr_log(f"Could not load influent time axis, using step index ({e}).")

    # --- Panels: (label, [columns], y-axis title) --------------------------
    panels = [
        ("Volatile fatty acids",
         ["S_va", "S_bu", "S_pro", "S_ac"], "kg COD / m^3"),
        ("pH",
         ["pH"], "pH"),
        ("Gas-phase concentrations",
         ["S_gas_h2", "S_gas_ch4", "S_gas_co2"], "conc."),
        ("Inorganic carbon & nitrogen",
         ["S_IC", "S_IN"], "kmole / m^3"),
    ]

    # Colour-blind-safe categorical palette.
    palette = ["#4E79A7", "#F28E2B", "#59A14F", "#E15759",
               "#B07AA1", "#76B7B2"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("PyADM1 anaerobic digestion — dynamic simulation results",
                 fontsize=15, fontweight="bold")

    for ax, (title, cols, ylab) in zip(axes.ravel(), panels):
        plotted = 0
        for i, col in enumerate(cols):
            if col in results.columns:
                ax.plot(x, results[col], label=col,
                        color=palette[i % len(palette)], linewidth=1.6)
                plotted += 1
        ax.set_title(title, fontsize=12)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylab)
        ax.grid(True, alpha=0.3)
        if plotted:
            ax.legend(fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig("adm1_outputs.png", dpi=150)
    plt.close(fig)

    # --- Upload figure -------------------------------------------------------
    faasr_put_file(local_folder=".", local_file="adm1_outputs.png",
                   remote_folder=folder, remote_file=plot_file)

    faasr_log(f"Visualization written to {folder}/{plot_file}.")
    return True
