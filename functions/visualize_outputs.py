import os

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless environments
import matplotlib.pyplot as plt
import pandas as pd


def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    """Visualize the PyADM1 dynamic simulation output time-series.

    Reads the ADM1 state-variable CSV produced by the `pyadm1` step
    (dynamic_out.csv), discovers the available columns dynamically, and
    renders a multi-panel figure of the state variables over simulation
    time steps. The figure is saved as a PNG and uploaded to S3.
    """
    faasr_log(f"visualize_outputs: starting visualization of '{input1}' in folder '{folder}'.")

    local_in = "dynamic_out.csv"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"visualize_outputs: required input '{input1}' is missing or empty."
        faasr_log(msg)
        raise FileNotFoundError(msg)

    # Load the simulation output. It is a wide CSV: one column per ADM1 state
    # variable, one row per simulation time step (no explicit time column).
    df = pd.read_csv(local_in)
    faasr_log(
        f"visualize_outputs: loaded {df.shape[0]} time steps and "
        f"{df.shape[1]} variables from '{input1}'."
    )

    if df.shape[0] == 0 or df.shape[1] == 0:
        msg = f"visualize_outputs: input '{input1}' contains no data to plot."
        faasr_log(msg)
        raise ValueError(msg)

    # Discover numeric variable columns dynamically (do not hardcode).
    numeric_df = df.apply(pd.to_numeric, errors="coerce")
    variable_cols = [c for c in numeric_df.columns if numeric_df[c].notna().any()]

    if not variable_cols:
        msg = f"visualize_outputs: no numeric variables found in '{input1}' to plot."
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"visualize_outputs: plotting {len(variable_cols)} variables: {variable_cols}")

    # Time axis: the output CSV has no explicit time column, so use the row
    # index as the (discrete) simulation time step.
    time_axis = range(len(numeric_df))

    # Group variables into logical panels so each figure is readable:
    #  - Soluble species (S_* excluding ions/gas/pH)
    #  - Particulate/biomass species (X_*)
    #  - Ionic species (*_ion) and inorganic carbon/nitrogen partitioning
    #  - Gas-phase species (S_gas_*)
    #  - pH (its own panel; different scale/units)
    def _classify(col):
        if col == "pH":
            return "pH"
        if col.startswith("S_gas_"):
            return "Gas-phase species"
        if col.endswith("_ion"):
            return "Ionic species"
        if col.startswith("X_"):
            return "Particulate / biomass species (X)"
        if col.startswith("S_"):
            return "Soluble species (S)"
        return "Other variables"

    groups = {}
    for col in variable_cols:
        groups.setdefault(_classify(col), []).append(col)

    # Deterministic, readable panel ordering.
    preferred_order = [
        "Soluble species (S)",
        "Particulate / biomass species (X)",
        "Ionic species",
        "Gas-phase species",
        "pH",
        "Other variables",
    ]
    panel_titles = [t for t in preferred_order if t in groups]
    for t in groups:
        if t not in panel_titles:
            panel_titles.append(t)

    n_panels = len(panel_titles)
    fig, axes = plt.subplots(
        n_panels, 1, figsize=(12, 4 * n_panels), squeeze=False
    )
    axes = axes[:, 0]

    for ax, title in zip(axes, panel_titles):
        cols = groups[title]
        for col in cols:
            ax.plot(time_axis, numeric_df[col].values, label=col, linewidth=1.2)
        ax.set_title(f"{title}")
        ax.set_xlabel("Simulation time step")
        if title == "pH":
            ax.set_ylabel("pH")
        else:
            ax.set_ylabel("Concentration / flow")
        ax.grid(True, linestyle="--", alpha=0.4)
        # Keep legends compact when there are many variables.
        ncol = 1 if len(cols) <= 6 else 2
        ax.legend(loc="best", fontsize="small", ncol=ncol)

    fig.suptitle("PyADM1 Simulation Outputs — ADM1 State Variables Over Time", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.99))

    local_out = "simulation_plots.png"
    fig.savefig(local_out, dpi=150, bbox_inches="tight")
    plt.close(fig)

    if not os.path.exists(local_out) or os.path.getsize(local_out) == 0:
        msg = "visualize_outputs: failed to render the output figure."
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(
        f"visualize_outputs: visualization complete. Figure with {n_panels} panels "
        f"written to '{output1}' in folder '{folder}'."
    )
