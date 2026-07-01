import os
import tempfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend — safe in serverless environments
import matplotlib.pyplot as plt


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "dynamic_out.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Simulation output CSV (dynamic_out.csv) must exist in S3 before visualization can proceed")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "adm1_results.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Multi-panel ADM1 results figure (adm1_results.png) must be present in S3 after visualization completes")
        raise SystemExit(1)
# --- end contract helpers ---


def visualize_results(folder: str, input1: str, output1: str) -> None:
    """Read pyadm1 simulation output (dynamic_out.csv) and produce a
    multi-panel PNG figure showing key ADM1 output trajectories over time.

    Panels:
      1. Biogas flow rate  (q_gas, m³ d⁻¹)
      2. Methane fraction  (% of dry biogas)
      3. Biogas-phase concentrations (S_gas_ch4, S_gas_co2, S_gas_h2)
      4. Volatile fatty acids (S_ac, S_pro, S_bu, S_va)
      5. Reactor pH
      6. Inorganic carbon (S_IC)
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("visualize_results: starting")

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "dynamic_out.csv")
        png_path = os.path.join(tmpdir, "adm1_results.png")

        # ------------------------------------------------------------------ #
        # Fetch simulation results from S3                                    #
        # ------------------------------------------------------------------ #
        faasr_get_file(local_file=csv_path, remote_folder=folder, remote_file=input1)

        df = pd.read_csv(csv_path)

        if df.empty:
            msg = "visualize_results: ERROR — simulation output CSV is empty"
            faasr_log(msg)
            raise ValueError(msg)

        faasr_log(
            f"visualize_results: loaded {len(df)} rows, {len(df.columns)} columns"
        )

        # ------------------------------------------------------------------ #
        # Time axis: row index corresponds to simulation day (0 … n_steps)   #
        # ------------------------------------------------------------------ #
        time = np.arange(len(df), dtype=float)

        # ------------------------------------------------------------------ #
        # Derived quantities — BSM2 constants from Rosen et al. (2006)       #
        # ------------------------------------------------------------------ #
        R       = 0.083145   # bar M⁻¹ K⁻¹
        T_op    = 308.15     # K  (35 °C)
        T_base  = 298.15     # K
        T_ad    = 308.15     # K
        p_atm   = 1.013      # bar
        k_p     = 5e4        # gas-phase pressure coefficient

        p_gas_h2o = 0.0313 * np.exp(5290.0 * (1.0 / T_base - 1.0 / T_ad))

        p_gas_h2  = df['S_gas_h2'].values  * R * T_op / 16.0
        p_gas_ch4 = df['S_gas_ch4'].values * R * T_op / 64.0
        p_gas_co2 = df['S_gas_co2'].values * R * T_op

        p_gas_total = p_gas_h2 + p_gas_ch4 + p_gas_co2 + p_gas_h2o

        # Biogas volumetric flow rate (m³ d⁻¹); negative values → 0
        q_gas = np.maximum(k_p * (p_gas_total - p_atm), 0.0)

        # Methane fraction in dry biogas (%)
        p_gas_dry = p_gas_total - p_gas_h2o
        with np.errstate(invalid='ignore', divide='ignore'):
            ch4_fraction = np.where(
                p_gas_dry > 0.0,
                p_gas_ch4 / p_gas_dry * 100.0,
                np.nan,
            )

        # ------------------------------------------------------------------ #
        # Multi-panel figure (3 rows × 2 columns)                            #
        # ------------------------------------------------------------------ #
        fig, axes = plt.subplots(3, 2, figsize=(14, 12))
        fig.suptitle(
            'ADM1 Simulation Results (BSM2 / Rosen et al. 2006)',
            fontsize=15, fontweight='bold', y=1.01,
        )

        # --- Panel 1: Biogas flow rate ---
        ax = axes[0, 0]
        ax.plot(time, q_gas, color='forestgreen', linewidth=1.5)
        ax.set_xlabel('Time (days)')
        ax.set_ylabel('$q_{gas}$ (m³ d⁻¹)')
        ax.set_title('Biogas Flow Rate')
        ax.grid(True, alpha=0.3)

        # --- Panel 2: Methane fraction ---
        ax = axes[0, 1]
        ax.plot(time, ch4_fraction, color='darkorange', linewidth=1.5)
        ax.set_xlabel('Time (days)')
        ax.set_ylabel('CH₄ fraction (%)')
        ax.set_title('Methane Fraction in Biogas')
        ax.grid(True, alpha=0.3)

        # --- Panel 3: Biogas-phase concentrations ---
        ax = axes[1, 0]
        ax.plot(time, df['S_gas_ch4'].values, label='$S_{gas,CH_4}$', linewidth=1.5)
        ax.plot(time, df['S_gas_co2'].values, label='$S_{gas,CO_2}$', linewidth=1.5)
        ax.plot(time, df['S_gas_h2'].values,  label='$S_{gas,H_2}$',  linewidth=1.5)
        ax.set_xlabel('Time (days)')
        ax.set_ylabel('Concentration (kg COD m⁻³ / kmol m⁻³)')
        ax.set_title('Biogas-Phase Concentrations')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # --- Panel 4: Volatile fatty acids ---
        ax = axes[1, 1]
        ax.plot(time, df['S_ac'].values,  label='$S_{ac}$',  linewidth=1.5)
        ax.plot(time, df['S_pro'].values, label='$S_{pro}$', linewidth=1.5)
        ax.plot(time, df['S_bu'].values,  label='$S_{bu}$',  linewidth=1.5)
        ax.plot(time, df['S_va'].values,  label='$S_{va}$',  linewidth=1.5)
        ax.set_xlabel('Time (days)')
        ax.set_ylabel('Concentration (kg COD m⁻³)')
        ax.set_title('Volatile Fatty Acids')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # --- Panel 5: pH ---
        ax = axes[2, 0]
        ax.plot(time, df['pH'].values, color='navy', linewidth=1.5)
        ax.set_xlabel('Time (days)')
        ax.set_ylabel('pH')
        ax.set_title('Reactor pH')
        ax.grid(True, alpha=0.3)

        # --- Panel 6: Inorganic carbon ---
        ax = axes[2, 1]
        ax.plot(time, df['S_IC'].values, color='saddlebrown', linewidth=1.5)
        ax.set_xlabel('Time (days)')
        ax.set_ylabel('$S_{IC}$ (kmol C m⁻³)')
        ax.set_title('Inorganic Carbon ($S_{IC}$)')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(png_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        faasr_log(f"visualize_results: figure saved ({png_path})")

        # ------------------------------------------------------------------ #
        # Upload result to S3                                                 #
        # ------------------------------------------------------------------ #
        faasr_put_file(local_file=png_path, remote_folder=folder, remote_file=output1)

    faasr_log("visualize_results: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---