import matplotlib
matplotlib.use("Agg")  # headless backend for the FaaSr runtime
import matplotlib.pyplot as plt
import pandas as pd


def visualize_adm1(folder, results_file, output_file):
    """
    FaaSr entry point: visualize the PyADM1 dynamic simulation outputs.

    Downloads the simulation results CSV from S3, builds a multi-panel dashboard
    of the key digester state variables and gas flows over time, and uploads the
    resulting PNG figure back to S3.
    """
    faasr_get_file(remote_folder=folder, remote_file=results_file,
                   local_file="dynamic_out.csv")

    df = pd.read_csv("dynamic_out.csv")

    # Use the 'time' column if run_pyadm1 wrote one; otherwise fall back to index.
    if "time" in df.columns:
        x = df["time"]
        xlabel = "time (d)"
    else:
        x = range(len(df))
        xlabel = "time step"

    # (column, human-readable title, y-axis label). Each is drawn only if present.
    panels = [
        ("pH", "Reactor pH", "pH"),
        ("q_ch4", "Methane gas flow", "q_ch4 (m^3/d)"),
        ("q_gas", "Total biogas flow", "q_gas (m^3/d)"),
        ("S_ac", "Acetate", "kg COD/m^3"),
        ("S_ch4", "Dissolved methane", "kg COD/m^3"),
        ("S_IN", "Inorganic nitrogen", "kmol N/m^3"),
        ("S_gas_ch4", "Gas-phase methane", "kg COD/m^3"),
        ("S_gas_co2", "Gas-phase CO2", "kmol C/m^3"),
        ("X_ac", "Acetate degraders", "kg COD/m^3"),
    ]
    panels = [p for p in panels if p[0] in df.columns]

    ncols = 3
    nrows = (len(panels) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 4 * nrows))
    axes = axes.flatten()

    for ax, (col, title, ylab) in zip(axes, panels):
        ax.plot(x, df[col], color="#2b8cbe", linewidth=1.6)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylab)
        ax.grid(True, alpha=0.3)

    # Hide any unused subplot axes.
    for ax in axes[len(panels):]:
        ax.axis("off")

    fig.suptitle("PyADM1 anaerobic digester dynamics", fontsize=16)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(output_file, dpi=120)
    plt.close(fig)

    faasr_put_file(local_file=output_file, remote_folder=folder,
                   remote_file=output_file)
    faasr_log(
        f"visualize_adm1: rendered {len(panels)} panels from {results_file}; "
        f"wrote {output_file} to {folder}"
    )
