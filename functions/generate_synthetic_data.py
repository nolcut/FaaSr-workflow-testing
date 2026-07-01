import os
import tempfile
import numpy as np
import pandas as pd


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "digester_influent.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Influent time-series CSV was not uploaded to S3 after generation")
        raise SystemExit(1)
    if "digester_initial.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Initial reactor conditions CSV was not uploaded to S3 after generation")
        raise SystemExit(1)
# --- end contract helpers ---


def generate_synthetic_data(folder: str, output1: str, output2: str) -> None:
    """
    Generate ADM1 influent time-series and initial reactor conditions based on
    the BSM2 benchmark values from Rosen et al. (2006) for use with pyadm1.

    Reference:
        Rosen, C., Jeppsson, U. (2006). Aspects on ADM1 Implementation within
        the BSM2 Framework. Dept. of Industrial Electrical Engineering and
        Automation, Lund University, Lund, Sweden.

    Parameters
    ----------
    folder  : S3 remote folder (FaaSr workflow folder)
    output1 : remote filename for the influent CSV  (digester_influent.csv)
    output2 : remote filename for the initial-state CSV (digester_initial.csv)
    """
    faasr_log("Generating ADM1 influent and initial conditions (BSM2 benchmark)")

    # ------------------------------------------------------------------
    # Influent state — BSM2 steady-state influent composition
    # Table A4, Rosen et al. (2006)
    # Units: kg COD m⁻³ for organic fractions; kmol m⁻³ for inorganic species
    # ------------------------------------------------------------------
    influent_ss = {
        'S_su':     0.01,       # monosaccharides
        'S_aa':     0.001,      # amino acids
        'S_fa':     0.001,      # total long-chain fatty acids
        'S_va':     0.001,      # total valerate
        'S_bu':     0.001,      # total butyrate
        'S_pro':    0.001,      # total propionate
        'S_ac':     0.001,      # total acetate
        'S_h2':     1.0e-8,     # dissolved hydrogen
        'S_ch4':    1.0e-5,     # dissolved methane
        'S_IC':     0.04,       # inorganic carbon  (kmol C m⁻³)
        'S_IN':     0.01,       # inorganic nitrogen (kmol N m⁻³)
        'S_I':      0.02,       # soluble inerts
        'X_xc':     2.0,        # composites
        'X_ch':     5.0,        # carbohydrates
        'X_pr':     20.0,       # proteins
        'X_li':     5.0,        # lipids
        'X_su':     0.0,        # sugar-degrading biomass
        'X_aa':     0.01,       # amino-acid-degrading biomass
        'X_fa':     0.0,        # LCFA-degrading biomass
        'X_c4':     0.0,        # C4-acid-degrading biomass
        'X_pro':    0.0,        # propionate-degrading biomass
        'X_ac':     0.0,        # acetate-degrading biomass
        'X_h2':     0.0,        # hydrogen-degrading biomass
        'X_I':      25.0,       # particulate inerts
        'S_cation': 0.04,       # cations  (kmol m⁻³)
        'S_anion':  0.02,       # anions   (kmol m⁻³)
    }

    # Simulation time vector: 200 daily steps (0 … 200 days).
    # pyadm1 uses t[0] as t₀ and integrates over t[1], t[2], … so the array
    # must have one more element than the number of integration intervals.
    n_steps = 200
    time_array = np.arange(0, n_steps + 1, dtype=float)   # shape (201,)
    Q_val = 178.4674   # m³ d⁻¹  — influent flow rate (BSM2 default)

    influent_data = {col: np.full(len(time_array), val)
                     for col, val in influent_ss.items()}
    influent_data['time'] = time_array
    influent_data['Q']    = np.full(len(time_array), Q_val)

    # Column order expected by pyadm1 / CONTEXT.md
    influent_cols = [
        'S_su', 'S_aa', 'S_fa', 'S_va', 'S_bu', 'S_pro', 'S_ac',
        'S_h2', 'S_ch4', 'S_IC', 'S_IN', 'S_I',
        'X_xc', 'X_ch', 'X_pr', 'X_li',
        'X_su', 'X_aa', 'X_fa', 'X_c4', 'X_pro', 'X_ac', 'X_h2', 'X_I',
        'S_cation', 'S_anion', 'time', 'Q',
    ]
    influent_df = pd.DataFrame(influent_data)[influent_cols]

    # ------------------------------------------------------------------
    # Initial reactor state — BSM2 steady-state values
    # Table A5, Rosen et al. (2006)
    # ------------------------------------------------------------------
    initial_vals = {
        'S_su':       1.2025e-2,    # kg COD m⁻³
        'S_aa':       5.3348e-3,
        'S_fa':       9.8601e-2,
        'S_va':       1.1612e-2,
        'S_bu':       1.3209e-2,
        'S_pro':      1.5781e-2,
        'S_ac':       1.9753e-1,
        'S_h2':       2.3424e-7,
        'S_ch4':      5.5141e-2,
        'S_IC':       1.5271e-1,    # kmol C m⁻³
        'S_IN':       1.3022e-1,    # kmol N m⁻³
        'S_I':        3.2870e-1,    # kg COD m⁻³
        'X_xc':       1.0799e-1,
        'X_ch':       2.0490e-2,
        'X_pr':       8.4183e-2,
        'X_li':       4.3629e-2,
        'X_su':       3.1229e-1,
        'X_aa':       9.3120e-1,
        'X_fa':       3.3817e-1,
        'X_c4':       3.3577e-1,
        'X_pro':      1.0117e-1,
        'X_ac':       6.7845e-1,
        'X_h2':       2.8398e-1,
        'X_I':        1.7207e+1,
        'S_cation':   0.04,         # kmol m⁻³
        'S_anion':    0.02,
        # Ion species (computed algebraically in BSM2 steady-state)
        'S_H_ion':    3.422e-8,     # kmol H m⁻³  →  pH ≈ 7.466
        'S_va_ion':   1.1588e-2,    # kg COD m⁻³
        'S_bu_ion':   1.3200e-2,
        'S_pro_ion':  1.5754e-2,
        'S_ac_ion':   1.9733e-1,
        'S_hco3_ion': 1.4191e-1,    # kmol C m⁻³
        'S_nh3':      4.1427e-3,    # kmol N m⁻³
        # Gas phase
        'S_gas_h2':   1.1032e-5,    # kg COD m⁻³
        'S_gas_ch4':  1.6517,       # kg COD m⁻³
        'S_gas_co2':  1.4116e-2,    # kmol C m⁻³
    }

    # Column order expected by pyadm1 / CONTEXT.md
    initial_cols = [
        'S_su', 'S_aa', 'S_fa', 'S_va', 'S_bu', 'S_pro', 'S_ac',
        'S_h2', 'S_ch4', 'S_IC', 'S_IN', 'S_I',
        'X_xc', 'X_ch', 'X_pr', 'X_li',
        'X_su', 'X_aa', 'X_fa', 'X_c4', 'X_pro', 'X_ac', 'X_h2', 'X_I',
        'S_cation', 'S_anion',
        'S_H_ion', 'S_va_ion', 'S_bu_ion', 'S_pro_ion', 'S_ac_ion',
        'S_hco3_ion', 'S_nh3',
        'S_gas_h2', 'S_gas_ch4', 'S_gas_co2',
    ]
    initial_df = pd.DataFrame([initial_vals])[initial_cols]

    # ------------------------------------------------------------------
    # Write to temp files and upload to S3
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        influent_path = os.path.join(tmpdir, "influent.csv")
        initial_path  = os.path.join(tmpdir, "initial.csv")

        influent_df.to_csv(influent_path, index=False)
        initial_df.to_csv(initial_path,  index=False)

        faasr_log(
            f"Uploading influent data ({len(influent_df)} rows, "
            f"{len(influent_df.columns)} columns) as '{output1}'"
        )
        faasr_put_file(
            local_file=influent_path,
            remote_folder=folder,
            remote_file=output1,
        )

        faasr_log(
            f"Uploading initial conditions (1 row, "
            f"{len(initial_df.columns)} columns) as '{output2}'"
        )
        faasr_put_file(
            local_file=initial_path,
            remote_folder=folder,
            remote_file=output2,
        )

    faasr_log("generate_synthetic_data complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---