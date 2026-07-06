import os

import matplotlib
matplotlib.use("Agg")  # headless backend: the runtime has no display server
import matplotlib.pyplot as plt
import pandas as pd


def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    """Visualize the PyADM1 dynamic simulation output.

    Reads the simulation results CSV (input1 = 'dynamic_out.csv'), a time
    series of anaerobic-digester state variables (concentrations, pH, gas-phase
    species, etc.), and produces clearly labeled line plots of the key state
    variables over the simulation time horizon, saved as a PNG (output1).
    """
    faasr_log("visualize_outputs: starting visualization of PyADM1 outputs")

    local_input = "dynamic_out.csv"
    local_output = "simulation_plots.png"

    # ---- Download the simulation results produced by the pyadm1 node --------
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_input) or os.path.getsize(local_input) == 0:
        msg = ("visualize_outputs: required input '%s' is missing or empty after "
               "download from folder '%s'" % (input1, folder))
        faasr_log(msg)
        raise FileNotFoundError(msg)

    # ---- Parse the results --------------------------------------------------
    df = pd.read_csv(local_input)
    if df.shape[0] == 0 or df.shape[1] == 0:
        msg = "visualize_outputs: parsed results '%s' contain no data" % input1
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log("visualize_outputs: loaded %d rows x %d columns from '%s'"
              % (df.shape[0], df.shape[1], input1))

    # The PyADM1 output stores one row per simulation time step. It does not
    # carry an explicit time column, so use the ordinal time-step index as the
    # x-axis (the simulation time horizon).
    if "time" in df.columns:
        x = df["time"].values
        x_label = "time [d]"
        state_cols = [c for c in df.columns if c != "time"]
    else:
        x = list(range(len(df)))
        x_label = "simulation time step"
        state_cols = list(df.columns)

    # Keep only numeric state variables that are actually present in the file.
    numeric_cols = [c for c in state_cols
                    if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        msg = "visualize_outputs: no numeric state variables found in '%s'" % input1
        faasr_log(msg)
        raise ValueError(msg)

    # ---- Group the key state variables into clearly labeled panels ----------
    # Each group lists variables expected in the ADM1/BSM2 state vector; only
    # those present in this particular file are drawn.
    groups = [
        ("Soluble substrates (kg COD / m^3)",
         ["S_su", "S_aa", "S_fa"], "concentration [kg COD/m^3]"),
        ("Volatile fatty acids (kg COD / m^3)",
         ["S_va", "S_bu", "S_pro", "S_ac"], "concentration [kg COD/m^3]"),
        ("Dissolved gases & inorganics",
         ["S_h2", "S_ch4", "S_IC", "S_IN"], "concentration"),
        ("Biomass / particulates (kg COD / m^3)",
         ["X_su", "X_aa", "X_fa", "X_c4", "X_pro", "X_ac", "X_h2",
          "X_xc", "X_ch", "X_pr", "X_li", "X_I"], "concentration [kg COD/m^3]"),
        ("pH",
         ["pH"], "pH"),
        ("Gas-phase species",
         ["S_gas_h2", "S_gas_ch4", "S_gas_co2"], "gas-phase concentration"),
    ]

    # Only keep groups that have at least one variable present in the file.
    present = set(numeric_cols)
    active_groups = []
    for title, cols, ylabel in groups:
        avail = [c for c in cols if c in present]
        if avail:
            active_groups.append((title, avail, ylabel))

    # Any numeric column not covered by a named group gets its own catch-all
    # panel so nothing is silently dropped from the visualization.
    covered = set()
    for _, cols, _ in active_groups:
        covered.update(cols)
    leftover = [c for c in numeric_cols if c not in covered]
    if leftover:
        active_groups.append(("Other state variables", leftover, "value"))

    if not active_groups:
        msg = "visualize_outputs: nothing plottable in '%s'" % input1
        faasr_log(msg)
        raise ValueError(msg)

    # ---- Build the figure ---------------------------------------------------
    n_panels = len(active_groups)
    n_cols = 2 if n_panels > 1 else 1
    n_rows = (n_panels + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(7.5 * n_cols, 4.0 * n_rows),
                             squeeze=False)
    fig.suptitle("PyADM1 anaerobic digester simulation: state variable dynamics",
                 fontsize=15, fontweight="bold")

    for idx, (title, cols, ylabel) in enumerate(active_groups):
        ax = axes[idx // n_cols][idx % n_cols]
        for c in cols:
            ax.plot(x, df[c].values, label=c, linewidth=1.3)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel(x_label)
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.legend(fontsize=8, ncol=2, loc="best")

    # Hide any unused axes in the grid.
    for empty in range(n_panels, n_rows * n_cols):
        axes[empty // n_cols][empty % n_cols].axis("off")

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(local_output, dpi=120)
    plt.close(fig)

    if not os.path.exists(local_output) or os.path.getsize(local_output) == 0:
        msg = "visualize_outputs: failed to produce a non-empty plot image"
        faasr_log(msg)
        raise RuntimeError(msg)

    # ---- Upload the visualization ------------------------------------------
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log("visualize_outputs: wrote visualization to '%s' (%d panels)"
              % (output1, n_panels))
