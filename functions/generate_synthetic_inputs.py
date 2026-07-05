import os
import numpy as np
import pandas as pd


def generate_synthetic_inputs(folder: str, output1: str, output2: str) -> None:
    """
    Generate synthetic ADM1 influent and initial state variable files based on the
    standard BSM2 (Benchmark Simulation Model No. 2) reference values from
    Rosen et al. (2006), Table B.1 (influent) and Table B.2 (steady-state initial
    conditions).  These are the canonical reference values used throughout the
    scientific literature for ADM1 validation studies.

    Outputs
    -------
    output1 : digester_influent.csv
        Time-series of influent state variables (constant steady-state composition
        over a 200-day horizon at 1-day intervals).  Columns match what
        pyadm1.py reads via setInfluent():
            S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac, S_h2, S_ch4,
            S_IC, S_IN, S_I, X_xc, X_ch, X_pr, X_li, X_su, X_aa, X_fa,
            X_c4, X_pro, X_ac, X_h2, X_I, S_cation, S_anion, Q, time

    output2 : digester_initial.csv
        Single-row initial reactor state for the ODE system.  Columns match
        what pyadm1.py reads at start-up:
            S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac, S_h2, S_ch4,
            S_IC, S_IN, S_I, X_xc, X_ch, X_pr, X_li, X_su, X_aa, X_fa,
            X_c4, X_pro, X_ac, X_h2, X_I, S_cation, S_anion,
            S_H_ion, S_va_ion, S_bu_ion, S_pro_ion, S_ac_ion, S_hco3_ion,
            S_nh3, S_gas_h2, S_gas_ch4, S_gas_co2
    """

    faasr_log("generate_synthetic_inputs: building BSM2 ADM1 reference inputs")

    # ------------------------------------------------------------------
    # BSM2 ADM1 steady-state influent composition
    # Source: Rosen et al. (2006), Benchmark Simulation Model No. 2 (BSM2),
    #         Department of Industrial Electrical Engineering and Automation,
    #         Lund University.  Table B.1.
    # Units are kg COD m^-3 except where noted.
    # ------------------------------------------------------------------

    # Soluble organic components (kg COD m^-3)
    S_su_in   = 0.01       # monosaccharides
    S_aa_in   = 0.001      # amino acids
    S_fa_in   = 0.001      # total long-chain fatty acids
    S_va_in   = 0.001      # total valerate
    S_bu_in   = 0.001      # total butyrate
    S_pro_in  = 0.001      # total propionate
    S_ac_in   = 0.001      # total acetate
    S_h2_in   = 1.0e-8     # dissolved hydrogen
    S_ch4_in  = 1.0e-5     # dissolved methane

    # Inorganic components
    S_IC_in   = 0.04       # inorganic carbon  (kmol C m^-3)
    S_IN_in   = 0.01       # inorganic nitrogen (kmol N m^-3)
    S_I_in    = 0.02       # soluble inerts    (kg COD m^-3)

    # Particulate components (kg COD m^-3)
    X_xc_in   = 2.0        # composites
    X_ch_in   = 5.0        # carbohydrates
    X_pr_in   = 20.0       # proteins
    X_li_in   = 5.0        # lipids
    X_su_in   = 0.0        # sugar degraders
    X_aa_in   = 0.01       # amino-acid degraders
    X_fa_in   = 0.0        # LCFA degraders
    X_c4_in   = 0.0        # valerate/butyrate degraders
    X_pro_in  = 0.0        # propionate degraders
    X_ac_in   = 0.0        # acetate degraders
    X_h2_in   = 0.0        # hydrogen degraders
    X_I_in    = 25.0       # particulate inerts

    # Ion concentrations (kmol m^-3)
    S_cation_in = 0.04     # cations (strong base)
    S_anion_in  = 0.02     # anions  (strong acid)

    # Volumetric flow rate (m^3 d^-1) — BSM2 default
    Q = 178.4674

    # ------------------------------------------------------------------
    # Build the influent time-series
    # 200 time steps, one per day (days 0 … 200 inclusive = 201 rows).
    # The downstream pyadm1.py iterates over t[1:], so day 0 is the
    # "pre-simulation" influent snapshot only.
    # ------------------------------------------------------------------
    n_steps = 200
    time_arr = np.arange(0, n_steps + 1, dtype=float)  # 0, 1, …, 200

    n_rows = len(time_arr)
    influent_data = {
        "S_su":      np.full(n_rows, S_su_in),
        "S_aa":      np.full(n_rows, S_aa_in),
        "S_fa":      np.full(n_rows, S_fa_in),
        "S_va":      np.full(n_rows, S_va_in),
        "S_bu":      np.full(n_rows, S_bu_in),
        "S_pro":     np.full(n_rows, S_pro_in),
        "S_ac":      np.full(n_rows, S_ac_in),
        "S_h2":      np.full(n_rows, S_h2_in),
        "S_ch4":     np.full(n_rows, S_ch4_in),
        "S_IC":      np.full(n_rows, S_IC_in),
        "S_IN":      np.full(n_rows, S_IN_in),
        "S_I":       np.full(n_rows, S_I_in),
        "X_xc":      np.full(n_rows, X_xc_in),
        "X_ch":      np.full(n_rows, X_ch_in),
        "X_pr":      np.full(n_rows, X_pr_in),
        "X_li":      np.full(n_rows, X_li_in),
        "X_su":      np.full(n_rows, X_su_in),
        "X_aa":      np.full(n_rows, X_aa_in),
        "X_fa":      np.full(n_rows, X_fa_in),
        "X_c4":      np.full(n_rows, X_c4_in),
        "X_pro":     np.full(n_rows, X_pro_in),
        "X_ac":      np.full(n_rows, X_ac_in),
        "X_h2":      np.full(n_rows, X_h2_in),
        "X_I":       np.full(n_rows, X_I_in),
        "S_cation":  np.full(n_rows, S_cation_in),
        "S_anion":   np.full(n_rows, S_anion_in),
        "Q":         np.full(n_rows, Q),
        "time":      time_arr,
    }
    influent_df = pd.DataFrame(influent_data)

    # ------------------------------------------------------------------
    # BSM2 ADM1 steady-state initial reactor conditions
    # Source: Rosen et al. (2006) Table B.2 — steady-state dynamic
    #         simulation output used as standard initial conditions.
    # ------------------------------------------------------------------

    # Soluble organic components (kg COD m^-3)
    S_su   = 0.012394
    S_aa   = 0.0055432
    S_fa   = 0.1074
    S_va   = 0.012395
    S_bu   = 0.013732
    S_pro  = 0.017584
    S_ac   = 0.089315
    S_h2   = 2.5055e-7
    S_ch4  = 0.055

    # Inorganic
    S_IC   = 0.15436    # kmol C m^-3
    S_IN   = 0.13024    # kmol N m^-3
    S_I    = 0.13222    # kg COD m^-3

    # Particulate (kg COD m^-3)
    X_xc   = 0.10791
    X_ch   = 0.020517
    X_pr   = 0.084112
    X_li   = 0.043629
    X_su   = 0.31219
    X_aa   = 0.93191
    X_fa   = 0.33827
    X_c4   = 0.33537
    X_pro  = 0.10112
    X_ac   = 0.67761
    X_h2   = 0.28484
    X_I    = 17.2162

    # Ions / cations / anions
    S_cation  = 0.04        # kmol m^-3
    S_anion   = 0.02        # kmol m^-3

    # DAE-derived ion states
    # pH = 7.4655 → S_H_ion = 10^-7.4655
    S_H_ion   = 3.4227e-8   # kmol H m^-3
    S_va_ion  = 0.011611    # kg COD m^-3
    S_bu_ion  = 0.013237    # kg COD m^-3
    S_pro_ion = 0.017056    # kg COD m^-3
    S_ac_ion  = 0.086831    # kg COD m^-3
    S_hco3_ion = 0.14253    # kmol C m^-3
    S_nh3     = 0.0041282   # kmol N m^-3

    # Gas-phase variables
    S_gas_h2  = 1.1032e-5   # kg COD m^-3
    S_gas_ch4 = 1.6535      # kg COD m^-3
    S_gas_co2 = 0.013761    # kmol C m^-3

    initial_data = {
        "S_su":       [S_su],
        "S_aa":       [S_aa],
        "S_fa":       [S_fa],
        "S_va":       [S_va],
        "S_bu":       [S_bu],
        "S_pro":      [S_pro],
        "S_ac":       [S_ac],
        "S_h2":       [S_h2],
        "S_ch4":      [S_ch4],
        "S_IC":       [S_IC],
        "S_IN":       [S_IN],
        "S_I":        [S_I],
        "X_xc":       [X_xc],
        "X_ch":       [X_ch],
        "X_pr":       [X_pr],
        "X_li":       [X_li],
        "X_su":       [X_su],
        "X_aa":       [X_aa],
        "X_fa":       [X_fa],
        "X_c4":       [X_c4],
        "X_pro":      [X_pro],
        "X_ac":       [X_ac],
        "X_h2":       [X_h2],
        "X_I":        [X_I],
        "S_cation":   [S_cation],
        "S_anion":    [S_anion],
        "S_H_ion":    [S_H_ion],
        "S_va_ion":   [S_va_ion],
        "S_bu_ion":   [S_bu_ion],
        "S_pro_ion":  [S_pro_ion],
        "S_ac_ion":   [S_ac_ion],
        "S_hco3_ion": [S_hco3_ion],
        "S_nh3":      [S_nh3],
        "S_gas_h2":   [S_gas_h2],
        "S_gas_ch4":  [S_gas_ch4],
        "S_gas_co2":  [S_gas_co2],
    }
    initial_df = pd.DataFrame(initial_data)

    # ------------------------------------------------------------------
    # Save locally and upload to S3 via FaaSr
    # ------------------------------------------------------------------
    local_influent = "digester_influent.csv"
    local_initial  = "digester_initial.csv"

    influent_df.to_csv(local_influent, index=False)
    faasr_log(
        f"generate_synthetic_inputs: wrote influent file "
        f"({n_rows} rows × {len(influent_df.columns)} columns)"
    )

    initial_df.to_csv(local_initial, index=False)
    faasr_log(
        "generate_synthetic_inputs: wrote initial-conditions file (1 row)"
    )

    faasr_put_file(local_file=local_influent, remote_folder=folder, remote_file=output1)
    faasr_log(f"generate_synthetic_inputs: uploaded {output1} to {folder}")

    faasr_put_file(local_file=local_initial, remote_folder=folder, remote_file=output2)
    faasr_log(f"generate_synthetic_inputs: uploaded {output2} to {folder}")

    # Clean up local temp files
    for f in (local_influent, local_initial):
        if os.path.exists(f):
            os.remove(f)

    faasr_log("generate_synthetic_inputs: complete")
