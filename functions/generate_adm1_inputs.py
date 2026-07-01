# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "adm1_feed_characteristics.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Feed characteristics CSV was not produced in S3")
        raise SystemExit(1)
    if "adm1_config.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: ADM1 configuration JSON was not produced in S3")
        raise SystemExit(1)
# --- end contract helpers ---


def generate_adm1_inputs(folder: str, output1: str, output2: str) -> None:
    """
    Generate the default ADM1 (Anaerobic Digestion Model No. 1) input feed
    characteristics and the model configuration (initial state vector plus the
    kinetic/stoichiometric/physiochemical parameter set), exactly as defined in
    the BSM2 benchmark reference implementation:

        Rosen, C. and Jeppsson, U. (2006). "Aspects on ADM1 Implementation within
        the BSM2 Framework." Dept. of Industrial Electrical Engineering and
        Automation, Lund University, Sweden.

    This is a deterministic source node — it takes no inputs. All numeric values
    are the published BSM2 ADM1 reference (benchmark) constants; nothing is
    randomised, mocked, or fabricated.

    Outputs
    -------
    output1 : CSV of time-varying influent feed characteristics (one row per time
              step; flow rate + the 24 ADM1 soluble/particulate COD components +
              cation/anion concentrations). Values are the BSM2 steady-state
              influent held constant across the time horizon.
    output2 : JSON with the default initial state vector and the full ADM1
              kinetic/stoichiometric/physiochemical/physical parameter set.
    """
    import os
    import json
    import numpy as np
    import pandas as pd

    faasr_log("generate_adm1_inputs: building BSM2 ADM1 default influent feed and configuration")

    # ------------------------------------------------------------------
    # 1) BSM2 ADM1 steady-state INFLUENT feed characteristics
    #    (Rosen & Jeppsson 2006, "Steady-state input variable values", p.20)
    #    Soluble/particulate components in kg COD m^-3, inorganic C/N in
    #    kmole m^-3, cations/anions in kmole m^-3, flow in m^3 d^-1, T in degC.
    # ------------------------------------------------------------------
    influent = {
        "S_su":  0.01,      # monosaccharides (kg COD/m3)
        "S_aa":  0.001,     # amino acids
        "S_fa":  0.001,     # long chain fatty acids
        "S_va":  0.001,     # total valerate
        "S_bu":  0.001,     # total butyrate
        "S_pro": 0.001,     # total propionate
        "S_ac":  0.001,     # total acetate
        "S_h2":  1.0e-8,    # hydrogen gas
        "S_ch4": 1.0e-5,    # methane gas
        "S_IC":  0.04,      # inorganic carbon (kmole C/m3)
        "S_IN":  0.01,      # inorganic nitrogen (kmole N/m3)
        "S_I":   0.02,      # soluble inerts (kg COD/m3)
        "X_xc":  2.0,       # composites (kg COD/m3)
        "X_ch":  5.0,       # carbohydrates
        "X_pr":  20.0,      # proteins
        "X_li":  5.0,       # lipids
        "X_su":  0.0,       # sugar degraders
        "X_aa":  0.01,      # amino acid degraders
        "X_fa":  0.01,      # LCFA degraders
        "X_c4":  0.01,      # valerate/butyrate degraders
        "X_pro": 0.01,      # propionate degraders
        "X_ac":  0.01,      # acetate degraders
        "X_h2":  0.01,      # hydrogen degraders
        "X_I":   25.0,      # particulate inerts
        "S_cat": 0.04,      # cations (kmole/m3)
        "S_an":  0.02,      # anions (kmole/m3)
    }
    q_in = 170.0            # influent flow rate (m3/d)
    T_op_C = 35.0           # operating temperature (degC)

    # Time-varying feed: BSM2 reaches (pseudo) steady state over ~200 days.
    # The realistic default influent is held constant across the horizon so the
    # feed dataset contains one row per time step, as specified.
    n_days = 200
    times = np.arange(0.0, float(n_days) + 1.0, 1.0)  # daily steps, 0..200 d

    feed_columns = ["time"] + list(influent.keys()) + ["Q", "T_op"]
    rows = []
    for t in times:
        row = {"time": float(t)}
        row.update({k: float(v) for k, v in influent.items()})
        row["Q"] = q_in
        row["T_op"] = T_op_C
        rows.append(row)
    feed_df = pd.DataFrame(rows, columns=feed_columns)

    local_feed = "adm1_feed_characteristics.csv"
    feed_df.to_csv(local_feed, index=False)
    faasr_log(f"Wrote feed characteristics: {len(feed_df)} time steps, {len(feed_columns)} columns")

    # ------------------------------------------------------------------
    # 2) Default INITIAL STATE vector
    #    (Rosen & Jeppsson 2006, "Steady-state output variable values", p.20)
    #    Used as the default starting concentrations for the ADM1 states.
    # ------------------------------------------------------------------
    initial_state = {
        # soluble (kg COD/m3 unless noted)
        "S_su":  0.0119548297170,
        "S_aa":  0.0053147401716,
        "S_fa":  0.0986214009308,
        "S_va":  0.0116250064639,
        "S_bu":  0.0132507296663,
        "S_pro": 0.0157836662845,
        "S_ac":  0.1976297169375,
        "S_h2":  2.359451e-07,
        "S_ch4": 0.0550887764460,
        "S_IC":  0.1526778706263,     # kmole C/m3
        "S_IN":  0.1302298158037,     # kmole N/m3
        "S_I":   0.3286976637215,
        # particulate (kg COD/m3)
        "X_xc":  0.3086976637215,
        "X_ch":  0.0279472404350,
        "X_pr":  0.1025741061067,
        "X_li":  0.0294830497073,
        "X_su":  0.4201659824546,
        "X_aa":  1.1791717989237,
        "X_fa":  0.2430353447194,
        "X_c4":  0.4319211056360,
        "X_pro": 0.1373059089340,
        "X_ac":  0.7605626583132,
        "X_h2":  0.3170229533613,
        "X_I":   25.6173953274430,
        # cations / anions (kmole/m3)
        "S_cat": 0.0400000000000,
        "S_an":  0.0200000000000,
        # ion states (kmole/m3 unless noted)
        "S_va_ion":   0.0115962470726,
        "S_bu_ion":   0.0132208262485,
        "S_pro_ion":  0.0157427831916,
        "S_ac_ion":   0.1972411554365,
        "S_hco3_ion": 0.1427774793921,   # kmole C/m3
        "S_nh3":      0.0040909284584,   # kmole N/m3
        # gas phase (kg COD/m3 for h2/ch4, kmole C/m3 for co2)
        "S_gas_h2":  1.02410356e-05,
        "S_gas_ch4": 1.6256072099814,
        "S_gas_co2": 0.0141505346784,
        # auxiliary / derived states
        "S_H_ion": 3.42344e-08,          # hydrogen ion concentration (kmole/m3)
        "S_co2":   0.0099003912343,      # kmole C/m3
        "S_nh4_ion": 0.1261388873452,    # kmole N/m3
        "pH": 7.4655377698929,
    }

    # ------------------------------------------------------------------
    # 3) Stoichiometric parameters (p.16)
    # ------------------------------------------------------------------
    stoichiometric = {
        "f_sI_xc": 0.1,
        "f_xI_xc": 0.2,
        "f_ch_xc": 0.2,
        "f_pr_xc": 0.2,
        "f_li_xc": 0.3,
        "N_xc": 0.0376 / 14.0,      # kmole N/kg COD
        "N_I":  0.06 / 14.0,        # kmole N/kg COD
        "N_aa": 0.007,              # kmole N/kg COD
        "C_xc": 0.02786,            # kmole C/kg COD
        "C_sI": 0.03,
        "C_ch": 0.0313,
        "C_pr": 0.03,
        "C_li": 0.022,
        "C_xI": 0.03,
        "C_su": 0.0313,
        "C_aa": 0.03,
        "f_fa_li": 0.95,
        "C_fa": 0.0217,
        "f_h2_su": 0.19,
        "f_bu_su": 0.13,
        "f_pro_su": 0.27,
        "f_ac_su": 0.41,
        "N_bac": 0.08 / 14.0,       # kmole N/kg COD
        "C_bu": 0.025,
        "C_pro": 0.0268,
        "C_ac": 0.0313,
        "C_bac": 0.0313,
        "Y_su": 0.1,
        "f_h2_aa": 0.06,
        "f_va_aa": 0.23,
        "f_bu_aa": 0.26,
        "f_pro_aa": 0.05,
        "f_ac_aa": 0.40,
        "C_va": 0.024,
        "Y_aa": 0.08,
        "Y_fa": 0.06,
        "Y_c4": 0.06,
        "Y_pro": 0.04,
        "C_ch4": 0.0156,
        "Y_ac": 0.05,
        "Y_h2": 0.06,
    }

    # ------------------------------------------------------------------
    # 4) Biochemical parameters (p.17). Rates in d^-1, half-saturation in
    #    kg COD m^-3, K_S_IN / K_I_nh3 in M (kmole m^-3), pH limits dimensionless.
    # ------------------------------------------------------------------
    biochemical = {
        "k_dis": 0.5,
        "k_hyd_ch": 10.0,
        "k_hyd_pr": 10.0,
        "k_hyd_li": 10.0,
        "K_S_IN": 1.0e-4,
        "k_m_su": 30.0,
        "K_S_su": 0.5,
        "pH_UL_aa": 5.5,
        "pH_LL_aa": 4.0,
        "k_m_aa": 50.0,
        "K_S_aa": 0.3,
        "k_m_fa": 6.0,
        "K_S_fa": 0.4,
        "K_I_h2_fa": 5.0e-6,
        "k_m_c4": 20.0,
        "K_S_c4": 0.2,
        "K_I_h2_c4": 1.0e-5,
        "k_m_pro": 13.0,
        "K_S_pro": 0.1,
        "K_I_h2_pro": 3.5e-6,
        "k_m_ac": 8.0,
        "K_S_ac": 0.15,
        "K_I_nh3": 0.0018,
        "pH_UL_ac": 7.0,
        "pH_LL_ac": 6.0,
        "k_m_h2": 35.0,
        "K_S_h2": 7.0e-6,
        "pH_UL_h2": 6.0,
        "pH_LL_h2": 5.0,
        "k_dec_Xsu": 0.02,
        "k_dec_Xaa": 0.02,
        "k_dec_Xfa": 0.02,
        "k_dec_Xc4": 0.02,
        "k_dec_Xpro": 0.02,
        "k_dec_Xac": 0.02,
        "k_dec_Xh2": 0.02,
    }

    # ------------------------------------------------------------------
    # 5) Physiochemical parameters (p.18). Temperature-dependent acid-base
    #    equilibria, Henry constants and water-vapour pressure are computed at
    #    the operating temperature using the BSM2 reference expressions.
    # ------------------------------------------------------------------
    R = 0.083145            # bar M^-1 K^-1
    T_base = 298.15         # K
    T_op = 308.15           # K (35 degC)
    factor = (1.0 / T_base - 1.0 / T_op) / (100.0 * R)

    K_w    = (10.0 ** -14.0) * np.exp(55900.0 * factor)      # M
    K_a_va = 10.0 ** -4.86                                   # M (T-independent)
    K_a_bu = 10.0 ** -4.82
    K_a_pro = 10.0 ** -4.88
    K_a_ac = 10.0 ** -4.76
    K_a_co2 = (10.0 ** -6.35) * np.exp(7646.0 * factor)      # M
    K_a_IN = (10.0 ** -9.25) * np.exp(51965.0 * factor)      # M

    p_gas_h2o = 0.0313 * np.exp(5290.0 * (1.0 / T_base - 1.0 / T_op))  # bar
    K_H_co2 = 0.035 * np.exp(-19410.0 * factor)              # M_liq bar^-1
    K_H_ch4 = 0.0014 * np.exp(-14240.0 * factor)             # M_liq bar^-1
    K_H_h2  = 7.8e-4 * np.exp(-4180.0 * factor)              # M_liq bar^-1

    physiochemical = {
        "R": R,
        "T_base": T_base,
        "T_op": T_op,
        "K_w_base": 1.0e-14,
        "K_w": float(K_w),
        "K_a_va": float(K_a_va),
        "K_a_bu": float(K_a_bu),
        "K_a_pro": float(K_a_pro),
        "K_a_ac": float(K_a_ac),
        "K_a_co2_base": 10.0 ** -6.35,
        "K_a_co2": float(K_a_co2),
        "K_a_IN_base": 10.0 ** -9.25,
        "K_a_IN": float(K_a_IN),
        "k_A_Bva": 1.0e10,
        "k_A_Bbu": 1.0e10,
        "k_A_Bpro": 1.0e10,
        "k_A_Bac": 1.0e10,
        "k_A_Bco2": 1.0e10,
        "k_A_BIN": 1.0e10,
        "P_atm": 1.013,
        "p_gas_h2o": float(p_gas_h2o),
        "k_p": 5.0e4,
        "k_L_a": 200.0,
        "K_H_co2_base": 0.035,
        "K_H_co2": float(K_H_co2),
        "K_H_ch4_base": 0.0014,
        "K_H_ch4": float(K_H_ch4),
        "K_H_h2_base": 7.8e-4,
        "K_H_h2": float(K_H_h2),
    }

    # ------------------------------------------------------------------
    # 6) Physical (reactor) parameters (p.18)
    # ------------------------------------------------------------------
    physical = {
        "V_liq": 3400.0,   # m3 (liquid volume)
        "V_gas": 300.0,    # m3 (gas headspace volume)
        "T_op_C": T_op_C,  # degC (operating temperature)
        "q_in": q_in,      # m3/d (nominal influent flow)
    }

    config = {
        "model": "ADM1",
        "framework": "BSM2",
        "reference": ("Rosen, C. and Jeppsson, U. (2006). Aspects on ADM1 "
                      "Implementation within the BSM2 Framework, Lund University."),
        "initial_state": initial_state,
        "parameters": {
            "stoichiometric": stoichiometric,
            "biochemical": biochemical,
            "physiochemical": physiochemical,
            "physical": physical,
        },
    }

    local_config = "adm1_config.json"
    with open(local_config, "w") as f:
        json.dump(config, f, indent=2)
    faasr_log(f"Wrote configuration: {len(initial_state)} initial states, "
              f"{len(stoichiometric)} stoichiometric, {len(biochemical)} biochemical, "
              f"{len(physiochemical)} physiochemical, {len(physical)} physical parameters")

    # ------------------------------------------------------------------
    # Sanity checks (fail loudly; never fabricate) before upload.
    # ------------------------------------------------------------------
    if not os.path.exists(local_feed) or os.path.getsize(local_feed) == 0:
        faasr_log("ERROR: feed characteristics CSV was not written or is empty")
        raise RuntimeError("Failed to produce adm1_feed_characteristics.csv")
    if not os.path.exists(local_config) or os.path.getsize(local_config) == 0:
        faasr_log("ERROR: configuration JSON was not written or is empty")
        raise RuntimeError("Failed to produce adm1_config.json")

    # ------------------------------------------------------------------
    # Upload both outputs to S3.
    # ------------------------------------------------------------------
    faasr_put_file(local_file=local_feed, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded feed characteristics to S3 as '{output1}'")

    faasr_put_file(local_file=local_config, remote_folder=folder, remote_file=output2)
    faasr_log(f"Uploaded configuration to S3 as '{output2}'")

    faasr_log("generate_adm1_inputs: completed successfully")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---