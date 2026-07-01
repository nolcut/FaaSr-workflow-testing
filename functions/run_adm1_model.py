# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "adm1_feed_characteristics.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Influent feed characteristics CSV 'adm1_feed_characteristics.csv' must exist in S3 before running the ADM1 simulation")
        raise SystemExit(1)
    if "adm1_config.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: ADM1 configuration JSON 'adm1_config.json' with initial state and parameters must exist in S3 before running the simulation")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "adm1_model_output.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: ADM1 model output time-series 'adm1_model_output.csv' must be produced in S3 after the simulation completes")
        raise SystemExit(1)
# --- end contract helpers ---


def run_adm1_model(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Execute the Anaerobic Digestion Model No. 1 (ADM1) simulation following the
    BSM2 benchmark implementation of Rosen & Jeppsson (2006), "Aspects on ADM1
    Implementation within the BSM2 Framework", Lund University.

    Reads
    -----
    input1 : CSV of time-varying influent feed characteristics (time, the 26 ADM1
             soluble/particulate influent components, flow Q, temperature T_op).
    input2 : JSON with the default initial state vector and the full ADM1
             kinetic/stoichiometric/physiochemical/physical parameter set.

    Writes
    ------
    output1 : CSV time-series (one row per simulation time step) of the 35 ADM1
              state variables plus derived outputs (pH, biogas flow rate q_gas,
              CH4/CO2 partial pressures and volume fractions).

    The full 35-state ODE system (equations 1-35 in the reference) is integrated
    with a stiff solver; S_H+ (and hence pH) is obtained algebraically from the
    charge balance at every evaluation.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    import os
    import json
    import math
    import numpy as np
    import pandas as pd
    from scipy.integrate import solve_ivp

    faasr_log("run_adm1_model: starting ADM1 (BSM2) simulation")

    # ------------------------------------------------------------------
    # 1) Download inputs from S3
    # ------------------------------------------------------------------
    local_feed = "adm1_feed_characteristics.csv"
    local_config = "adm1_config.json"

    faasr_get_file(local_file=local_feed, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_config, remote_folder=folder, remote_file=input2)

    if not os.path.exists(local_feed) or os.path.getsize(local_feed) == 0:
        faasr_log(f"ERROR: feed characteristics '{input1}' missing or empty after download")
        raise RuntimeError(f"Required input '{input1}' could not be retrieved from S3")
    if not os.path.exists(local_config) or os.path.getsize(local_config) == 0:
        faasr_log(f"ERROR: configuration '{input2}' missing or empty after download")
        raise RuntimeError(f"Required input '{input2}' could not be retrieved from S3")

    feed_df = pd.read_csv(local_feed)
    with open(local_config, "r") as f:
        config = json.load(f)

    faasr_log(f"Loaded feed ({len(feed_df)} rows, {feed_df.shape[1]} cols) and configuration")

    # ------------------------------------------------------------------
    # 2) Unpack configuration (fail loudly on any missing required block)
    # ------------------------------------------------------------------
    try:
        init = config["initial_state"]
        params = config["parameters"]
        st = params["stoichiometric"]
        bio = params["biochemical"]
        phy = params["physiochemical"]
        phys = params["physical"]
    except (KeyError, TypeError) as e:
        faasr_log(f"ERROR: configuration JSON is missing required ADM1 blocks: {e}")
        raise RuntimeError("adm1_config.json does not contain a valid ADM1 parameter set") from e

    # 35 integrated state variables, in the ODE order of the reference (eqs 1-35)
    STATE_NAMES = [
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
        "S_IC", "S_IN", "S_I",
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
        "X_ac", "X_h2", "X_I",
        "S_cat", "S_an",
        "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion", "S_nh3",
        "S_gas_h2", "S_gas_ch4", "S_gas_co2",
    ]

    missing = [k for k in STATE_NAMES if k not in init]
    if missing:
        faasr_log(f"ERROR: initial_state missing state variables: {missing}")
        raise RuntimeError("adm1_config.json initial_state is incomplete")

    y0 = np.array([float(init[k]) for k in STATE_NAMES], dtype=float)

    # ------------------------------------------------------------------
    # 3) Influent characteristics from the feed CSV
    #    Only the 26 water-phase components (states 0..25) have influent terms.
    #    Ion states (26..31) and gas states (32..34) have no influent.
    # ------------------------------------------------------------------
    if "time" not in feed_df.columns:
        faasr_log("ERROR: feed CSV has no 'time' column")
        raise RuntimeError("adm1_feed_characteristics.csv must contain a 'time' column")

    feed_df = feed_df.sort_values("time").reset_index(drop=True)
    t_feed = feed_df["time"].to_numpy(dtype=float)

    influent_names = STATE_NAMES[:26]  # S_su .. S_an
    for name in influent_names:
        if name not in feed_df.columns:
            faasr_log(f"ERROR: feed CSV missing influent column '{name}'")
            raise RuntimeError(f"adm1_feed_characteristics.csv missing required column '{name}'")
    if "Q" not in feed_df.columns:
        faasr_log("ERROR: feed CSV missing flow column 'Q'")
        raise RuntimeError("adm1_feed_characteristics.csv missing required column 'Q'")

    influent_arr = feed_df[influent_names].to_numpy(dtype=float)  # (n_feed, 26)
    q_arr = feed_df["Q"].to_numpy(dtype=float)                    # (n_feed,)

    def interp_col(t, col_values):
        # constant extrapolation outside the tabulated range
        return float(np.interp(t, t_feed, col_values))

    def influent_at(t):
        return np.array([interp_col(t, influent_arr[:, j]) for j in range(26)], dtype=float)

    def q_at(t):
        return interp_col(t, q_arr)

    # ------------------------------------------------------------------
    # 4) Parameters
    # ------------------------------------------------------------------
    def g(d, key):
        if key not in d:
            faasr_log(f"ERROR: parameter '{key}' missing from configuration")
            raise RuntimeError(f"adm1_config.json missing required parameter '{key}'")
        return float(d[key])

    # Stoichiometric
    f_sI_xc = g(st, "f_sI_xc"); f_xI_xc = g(st, "f_xI_xc"); f_ch_xc = g(st, "f_ch_xc")
    f_pr_xc = g(st, "f_pr_xc"); f_li_xc = g(st, "f_li_xc")
    N_xc = g(st, "N_xc"); N_I = g(st, "N_I"); N_aa = g(st, "N_aa")
    C_xc = g(st, "C_xc"); C_sI = g(st, "C_sI"); C_ch = g(st, "C_ch"); C_pr = g(st, "C_pr")
    C_li = g(st, "C_li"); C_xI = g(st, "C_xI"); C_su = g(st, "C_su"); C_aa = g(st, "C_aa")
    f_fa_li = g(st, "f_fa_li"); C_fa = g(st, "C_fa")
    f_h2_su = g(st, "f_h2_su"); f_bu_su = g(st, "f_bu_su"); f_pro_su = g(st, "f_pro_su")
    f_ac_su = g(st, "f_ac_su"); N_bac = g(st, "N_bac")
    C_bu = g(st, "C_bu"); C_pro = g(st, "C_pro"); C_ac = g(st, "C_ac"); C_bac = g(st, "C_bac")
    Y_su = g(st, "Y_su")
    f_h2_aa = g(st, "f_h2_aa"); f_va_aa = g(st, "f_va_aa"); f_bu_aa = g(st, "f_bu_aa")
    f_pro_aa = g(st, "f_pro_aa"); f_ac_aa = g(st, "f_ac_aa"); C_va = g(st, "C_va")
    Y_aa = g(st, "Y_aa"); Y_fa = g(st, "Y_fa"); Y_c4 = g(st, "Y_c4"); Y_pro = g(st, "Y_pro")
    C_ch4 = g(st, "C_ch4"); Y_ac = g(st, "Y_ac"); Y_h2 = g(st, "Y_h2")

    # Biochemical
    k_dis = g(bio, "k_dis")
    k_hyd_ch = g(bio, "k_hyd_ch"); k_hyd_pr = g(bio, "k_hyd_pr"); k_hyd_li = g(bio, "k_hyd_li")
    K_S_IN = g(bio, "K_S_IN")
    k_m_su = g(bio, "k_m_su"); K_S_su = g(bio, "K_S_su")
    pH_UL_aa = g(bio, "pH_UL_aa"); pH_LL_aa = g(bio, "pH_LL_aa")
    k_m_aa = g(bio, "k_m_aa"); K_S_aa = g(bio, "K_S_aa")
    k_m_fa = g(bio, "k_m_fa"); K_S_fa = g(bio, "K_S_fa"); K_I_h2_fa = g(bio, "K_I_h2_fa")
    k_m_c4 = g(bio, "k_m_c4"); K_S_c4 = g(bio, "K_S_c4"); K_I_h2_c4 = g(bio, "K_I_h2_c4")
    k_m_pro = g(bio, "k_m_pro"); K_S_pro = g(bio, "K_S_pro"); K_I_h2_pro = g(bio, "K_I_h2_pro")
    k_m_ac = g(bio, "k_m_ac"); K_S_ac = g(bio, "K_S_ac"); K_I_nh3 = g(bio, "K_I_nh3")
    pH_UL_ac = g(bio, "pH_UL_ac"); pH_LL_ac = g(bio, "pH_LL_ac")
    k_m_h2 = g(bio, "k_m_h2"); K_S_h2 = g(bio, "K_S_h2")
    pH_UL_h2 = g(bio, "pH_UL_h2"); pH_LL_h2 = g(bio, "pH_LL_h2")
    k_dec_Xsu = g(bio, "k_dec_Xsu"); k_dec_Xaa = g(bio, "k_dec_Xaa"); k_dec_Xfa = g(bio, "k_dec_Xfa")
    k_dec_Xc4 = g(bio, "k_dec_Xc4"); k_dec_Xpro = g(bio, "k_dec_Xpro")
    k_dec_Xac = g(bio, "k_dec_Xac"); k_dec_Xh2 = g(bio, "k_dec_Xh2")

    # Physiochemical
    R = g(phy, "R"); T_op = g(phy, "T_op")
    K_w = g(phy, "K_w")
    K_a_va = g(phy, "K_a_va"); K_a_bu = g(phy, "K_a_bu"); K_a_pro = g(phy, "K_a_pro")
    K_a_ac = g(phy, "K_a_ac"); K_a_co2 = g(phy, "K_a_co2"); K_a_IN = g(phy, "K_a_IN")
    k_A_Bva = g(phy, "k_A_Bva"); k_A_Bbu = g(phy, "k_A_Bbu"); k_A_Bpro = g(phy, "k_A_Bpro")
    k_A_Bac = g(phy, "k_A_Bac"); k_A_Bco2 = g(phy, "k_A_Bco2"); k_A_BIN = g(phy, "k_A_BIN")
    P_atm = g(phy, "P_atm"); p_gas_h2o = g(phy, "p_gas_h2o")
    k_p = g(phy, "k_p"); k_L_a = g(phy, "k_L_a")
    K_H_co2 = g(phy, "K_H_co2"); K_H_ch4 = g(phy, "K_H_ch4"); K_H_h2 = g(phy, "K_H_h2")

    # Physical
    V_liq = g(phys, "V_liq"); V_gas = g(phys, "V_gas")

    # pH-inhibition Hill exponents (hydrogen-ion based function; BSM2 choice)
    n_aa = 3.0 / (pH_UL_aa - pH_LL_aa)
    n_ac = 3.0 / (pH_UL_ac - pH_LL_ac)
    n_h2 = 3.0 / (pH_UL_h2 - pH_LL_h2)
    K_pH_aa = 10.0 ** (-(pH_LL_aa + pH_UL_aa) / 2.0)
    K_pH_ac = 10.0 ** (-(pH_LL_ac + pH_UL_ac) / 2.0)
    K_pH_h2 = 10.0 ** (-(pH_LL_h2 + pH_UL_h2) / 2.0)

    # Carbon-balance stoichiometric coefficients (s1..s13, eq. 10)
    s1 = -C_xc + f_sI_xc * C_sI + f_ch_xc * C_ch + f_pr_xc * C_pr + f_li_xc * C_li + f_xI_xc * C_xI
    s2 = -C_ch + C_su
    s3 = -C_pr + C_aa
    s4 = -C_li + (1.0 - f_fa_li) * C_su + f_fa_li * C_fa
    s5 = -C_su + (1.0 - Y_su) * (f_bu_su * C_bu + f_pro_su * C_pro + f_ac_su * C_ac) + Y_su * C_bac
    s6 = -C_aa + (1.0 - Y_aa) * (f_va_aa * C_va + f_bu_aa * C_bu + f_pro_aa * C_pro + f_ac_aa * C_ac) + Y_aa * C_bac
    s7 = -C_fa + (1.0 - Y_fa) * 0.7 * C_ac + Y_fa * C_bac
    s8 = -C_va + (1.0 - Y_c4) * 0.54 * C_pro + (1.0 - Y_c4) * 0.31 * C_ac + Y_c4 * C_bac
    s9 = -C_bu + (1.0 - Y_c4) * 0.8 * C_ac + Y_c4 * C_bac
    s10 = -C_pro + (1.0 - Y_pro) * 0.57 * C_ac + Y_pro * C_bac
    s11 = -C_ac + (1.0 - Y_ac) * C_ch4 + Y_ac * C_bac
    s12 = (1.0 - Y_h2) * C_ch4 + Y_h2 * C_bac
    s13 = -C_bac + C_xc

    # ------------------------------------------------------------------
    # 5) ODE right-hand side
    # ------------------------------------------------------------------
    def adm1_rhs(t, y):
        (S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac, S_h2, S_ch4, S_IC, S_IN, S_I,
         X_xc, X_ch, X_pr, X_li, X_su, X_aa, X_fa, X_c4, X_pro, X_ac, X_h2, X_I,
         S_cat, S_an, S_va_ion, S_bu_ion, S_pro_ion, S_ac_ion, S_hco3_ion, S_nh3,
         S_gas_h2, S_gas_ch4, S_gas_co2) = y

        Sin = influent_at(t)
        q_in = q_at(t)
        D = q_in / V_liq

        # --- Algebraic pH from charge balance ---
        S_nh4_ion = S_IN - S_nh3
        Theta = (S_cat + S_nh4_ion - S_hco3_ion
                 - S_ac_ion / 64.0 - S_pro_ion / 112.0 - S_bu_ion / 160.0
                 - S_va_ion / 208.0 - S_an)
        S_H_ion = -Theta / 2.0 + 0.5 * math.sqrt(Theta * Theta + 4.0 * K_w)
        if S_H_ion <= 0.0:
            S_H_ion = 1.0e-12
        S_co2 = S_IC - S_hco3_ion

        # --- Inhibition factors ---
        I_pH_aa = K_pH_aa ** n_aa / (S_H_ion ** n_aa + K_pH_aa ** n_aa)
        I_pH_ac = K_pH_ac ** n_ac / (S_H_ion ** n_ac + K_pH_ac ** n_ac)
        I_pH_h2 = K_pH_h2 ** n_h2 / (S_H_ion ** n_h2 + K_pH_h2 ** n_h2)
        I_IN_lim = 1.0 / (1.0 + K_S_IN / S_IN) if S_IN > 0.0 else 0.0
        I_h2_fa = 1.0 / (1.0 + S_h2 / K_I_h2_fa)
        I_h2_c4 = 1.0 / (1.0 + S_h2 / K_I_h2_c4)
        I_h2_pro = 1.0 / (1.0 + S_h2 / K_I_h2_pro)
        I_nh3 = 1.0 / (1.0 + S_nh3 / K_I_nh3)

        I5 = I_pH_aa * I_IN_lim
        I6 = I5
        I7 = I_pH_aa * I_IN_lim * I_h2_fa
        I8 = I_pH_aa * I_IN_lim * I_h2_c4
        I9 = I8
        I10 = I_pH_aa * I_IN_lim * I_h2_pro
        I11 = I_pH_ac * I_IN_lim * I_nh3
        I12 = I_pH_h2 * I_IN_lim

        # --- Biochemical process rates rho1..rho19 ---
        r1 = k_dis * X_xc
        r2 = k_hyd_ch * X_ch
        r3 = k_hyd_pr * X_pr
        r4 = k_hyd_li * X_li
        r5 = k_m_su * (S_su / (K_S_su + S_su)) * X_su * I5 if (K_S_su + S_su) > 0 else 0.0
        r6 = k_m_aa * (S_aa / (K_S_aa + S_aa)) * X_aa * I6 if (K_S_aa + S_aa) > 0 else 0.0
        r7 = k_m_fa * (S_fa / (K_S_fa + S_fa)) * X_fa * I7 if (K_S_fa + S_fa) > 0 else 0.0
        r8 = k_m_c4 * (S_va / (K_S_c4 + S_va)) * X_c4 * (S_va / (S_bu + S_va + 1.0e-6)) * I8 if (K_S_c4 + S_va) > 0 else 0.0
        r9 = k_m_c4 * (S_bu / (K_S_c4 + S_bu)) * X_c4 * (S_bu / (S_va + S_bu + 1.0e-6)) * I9 if (K_S_c4 + S_bu) > 0 else 0.0
        r10 = k_m_pro * (S_pro / (K_S_pro + S_pro)) * X_pro * I10 if (K_S_pro + S_pro) > 0 else 0.0
        r11 = k_m_ac * (S_ac / (K_S_ac + S_ac)) * X_ac * I11 if (K_S_ac + S_ac) > 0 else 0.0
        r12 = k_m_h2 * (S_h2 / (K_S_h2 + S_h2)) * X_h2 * I12 if (K_S_h2 + S_h2) > 0 else 0.0
        r13 = k_dec_Xsu * X_su
        r14 = k_dec_Xaa * X_aa
        r15 = k_dec_Xfa * X_fa
        r16 = k_dec_Xc4 * X_c4
        r17 = k_dec_Xpro * X_pro
        r18 = k_dec_Xac * X_ac
        r19 = k_dec_Xh2 * X_h2
        r_dec_sum = r13 + r14 + r15 + r16 + r17 + r18 + r19

        # --- Acid-base rates ---
        rA4 = k_A_Bva * (S_va_ion * (K_a_va + S_H_ion) - K_a_va * S_va)
        rA5 = k_A_Bbu * (S_bu_ion * (K_a_bu + S_H_ion) - K_a_bu * S_bu)
        rA6 = k_A_Bpro * (S_pro_ion * (K_a_pro + S_H_ion) - K_a_pro * S_pro)
        rA7 = k_A_Bac * (S_ac_ion * (K_a_ac + S_H_ion) - K_a_ac * S_ac)
        rA10 = k_A_Bco2 * (S_hco3_ion * (K_a_co2 + S_H_ion) - K_a_co2 * S_IC)
        rA11 = k_A_BIN * (S_nh3 * (K_a_IN + S_H_ion) - K_a_IN * S_IN)

        # --- Gas partial pressures and transfer rates ---
        p_gas_h2 = S_gas_h2 * R * T_op / 16.0
        p_gas_ch4 = S_gas_ch4 * R * T_op / 64.0
        p_gas_co2 = S_gas_co2 * R * T_op
        P_gas = p_gas_h2 + p_gas_ch4 + p_gas_co2 + p_gas_h2o
        q_gas = k_p * (P_gas - P_atm)
        if q_gas < 0.0:
            q_gas = 0.0

        rT8 = k_L_a * (S_h2 - 16.0 * K_H_h2 * p_gas_h2)
        rT9 = k_L_a * (S_ch4 - 64.0 * K_H_ch4 * p_gas_ch4)
        rT10 = k_L_a * (S_co2 - K_H_co2 * p_gas_co2)

        # --- Carbon balance sum for S_IC (eq. 10) ---
        carbon_sum = (s1 * r1 + s2 * r2 + s3 * r3 + s4 * r4 + s5 * r5 + s6 * r6
                      + s7 * r7 + s8 * r8 + s9 * r9 + s10 * r10 + s11 * r11
                      + s12 * r12 + s13 * r_dec_sum)

        dydt = np.empty(35, dtype=float)

        # Soluble matter (eqs 1-12)
        dydt[0] = D * (Sin[0] - S_su) + r2 + (1.0 - f_fa_li) * r4 - r5
        dydt[1] = D * (Sin[1] - S_aa) + r3 - r6
        dydt[2] = D * (Sin[2] - S_fa) + f_fa_li * r4 - r7
        dydt[3] = D * (Sin[3] - S_va) + (1.0 - Y_aa) * f_va_aa * r6 - r8
        dydt[4] = D * (Sin[4] - S_bu) + (1.0 - Y_su) * f_bu_su * r5 + (1.0 - Y_aa) * f_bu_aa * r6 - r9
        dydt[5] = (D * (Sin[5] - S_pro) + (1.0 - Y_su) * f_pro_su * r5
                   + (1.0 - Y_aa) * f_pro_aa * r6 + (1.0 - Y_c4) * 0.54 * r8 - r10)
        dydt[6] = (D * (Sin[6] - S_ac) + (1.0 - Y_su) * f_ac_su * r5
                   + (1.0 - Y_aa) * f_ac_aa * r6 + (1.0 - Y_fa) * 0.7 * r7
                   + (1.0 - Y_c4) * 0.31 * r8 + (1.0 - Y_c4) * 0.8 * r9
                   + (1.0 - Y_pro) * 0.57 * r10 - r11)
        dydt[7] = (D * (Sin[7] - S_h2) + (1.0 - Y_su) * f_h2_su * r5
                   + (1.0 - Y_aa) * f_h2_aa * r6 + (1.0 - Y_fa) * 0.3 * r7
                   + (1.0 - Y_c4) * 0.15 * r8 + (1.0 - Y_c4) * 0.2 * r9
                   + (1.0 - Y_pro) * 0.43 * r10 - r12 - rT8)
        dydt[8] = D * (Sin[8] - S_ch4) + (1.0 - Y_ac) * r11 + (1.0 - Y_h2) * r12 - rT9
        dydt[9] = D * (Sin[9] - S_IC) - carbon_sum - rT10
        dydt[10] = (D * (Sin[10] - S_IN)
                    - Y_su * N_bac * r5
                    + (N_aa - Y_aa * N_bac) * r6
                    - Y_fa * N_bac * r7
                    - Y_c4 * N_bac * r8
                    - Y_c4 * N_bac * r9
                    - Y_pro * N_bac * r10
                    - Y_ac * N_bac * r11
                    - Y_h2 * N_bac * r12
                    + (N_bac - N_xc) * r_dec_sum
                    + (N_xc - f_xI_xc * N_I - f_sI_xc * N_I - f_pr_xc * N_aa) * r1)
        dydt[11] = D * (Sin[11] - S_I) + f_sI_xc * r1

        # Particulate matter (eqs 13-24)
        dydt[12] = D * (Sin[12] - X_xc) - r1 + r_dec_sum
        dydt[13] = D * (Sin[13] - X_ch) + f_ch_xc * r1 - r2
        dydt[14] = D * (Sin[14] - X_pr) + f_pr_xc * r1 - r3
        dydt[15] = D * (Sin[15] - X_li) + f_li_xc * r1 - r4
        dydt[16] = D * (Sin[16] - X_su) + Y_su * r5 - r13
        dydt[17] = D * (Sin[17] - X_aa) + Y_aa * r6 - r14
        dydt[18] = D * (Sin[18] - X_fa) + Y_fa * r7 - r15
        dydt[19] = D * (Sin[19] - X_c4) + Y_c4 * r8 + Y_c4 * r9 - r16
        dydt[20] = D * (Sin[20] - X_pro) + Y_pro * r10 - r17
        dydt[21] = D * (Sin[21] - X_ac) + Y_ac * r11 - r18
        dydt[22] = D * (Sin[22] - X_h2) + Y_h2 * r12 - r19
        dydt[23] = D * (Sin[23] - X_I) + f_xI_xc * r1

        # Cations and anions (eqs 25-26)
        dydt[24] = D * (Sin[24] - S_cat)
        dydt[25] = D * (Sin[25] - S_an)

        # Ion states (eqs 27-32) — no dilution term
        dydt[26] = -rA4
        dydt[27] = -rA5
        dydt[28] = -rA6
        dydt[29] = -rA7
        dydt[30] = -rA10
        dydt[31] = -rA11

        # Gas phase (eqs 33-35)
        dydt[32] = -S_gas_h2 * q_gas / V_gas + rT8 * V_liq / V_gas
        dydt[33] = -S_gas_ch4 * q_gas / V_gas + rT9 * V_liq / V_gas
        dydt[34] = -S_gas_co2 * q_gas / V_gas + rT10 * V_liq / V_gas

        return dydt

    # ------------------------------------------------------------------
    # 6) Integrate over the feed time horizon (stiff solver)
    # ------------------------------------------------------------------
    t0 = float(t_feed[0])
    tf = float(t_feed[-1])
    if tf <= t0:
        faasr_log("ERROR: feed time column does not define a positive simulation horizon")
        raise RuntimeError("Feed 'time' column must span an increasing simulation horizon")

    faasr_log(f"Integrating 35-state ADM1 ODE system from t={t0} to t={tf} d (stiff BDF solver)")

    sol = solve_ivp(
        adm1_rhs, (t0, tf), y0,
        method="BDF",
        t_eval=t_feed,
        rtol=1.0e-6,
        atol=1.0e-8,
        max_step=1.0,
    )

    if not sol.success:
        faasr_log(f"ERROR: ODE integration failed: {sol.message}")
        raise RuntimeError(f"ADM1 ODE integration failed: {sol.message}")

    faasr_log(f"Integration succeeded: {sol.y.shape[1]} time points produced")

    # ------------------------------------------------------------------
    # 7) Assemble output time-series with derived variables
    # ------------------------------------------------------------------
    times = sol.t
    Y = sol.y  # (35, n)

    records = []
    for idx in range(len(times)):
        y = Y[:, idx]
        row = {"time": float(times[idx])}
        for j, name in enumerate(STATE_NAMES):
            row[name] = float(y[j])

        # Derived: pH, ammonium, dissolved CO2, gas pressures/flow/composition
        S_IN = y[10]; S_IC = y[9]
        S_cat = y[24]; S_an = y[25]
        S_va_ion = y[26]; S_bu_ion = y[27]; S_pro_ion = y[28]; S_ac_ion = y[29]
        S_hco3_ion = y[30]; S_nh3 = y[31]
        S_gas_h2 = y[32]; S_gas_ch4 = y[33]; S_gas_co2 = y[34]

        S_nh4_ion = S_IN - S_nh3
        Theta = (S_cat + S_nh4_ion - S_hco3_ion
                 - S_ac_ion / 64.0 - S_pro_ion / 112.0 - S_bu_ion / 160.0
                 - S_va_ion / 208.0 - S_an)
        S_H_ion = -Theta / 2.0 + 0.5 * math.sqrt(Theta * Theta + 4.0 * K_w)
        if S_H_ion <= 0.0:
            S_H_ion = 1.0e-12
        pH = -math.log10(S_H_ion)
        S_co2 = S_IC - S_hco3_ion

        p_gas_h2 = S_gas_h2 * R * T_op / 16.0
        p_gas_ch4 = S_gas_ch4 * R * T_op / 64.0
        p_gas_co2 = S_gas_co2 * R * T_op
        P_gas = p_gas_h2 + p_gas_ch4 + p_gas_co2 + p_gas_h2o
        q_gas = k_p * (P_gas - P_atm)
        if q_gas < 0.0:
            q_gas = 0.0

        frac_ch4 = p_gas_ch4 / P_gas if P_gas > 0.0 else 0.0
        frac_co2 = p_gas_co2 / P_gas if P_gas > 0.0 else 0.0

        row["S_H_ion"] = float(S_H_ion)
        row["pH"] = float(pH)
        row["S_nh4_ion"] = float(S_nh4_ion)
        row["S_co2"] = float(S_co2)
        row["p_gas_h2"] = float(p_gas_h2)
        row["p_gas_ch4"] = float(p_gas_ch4)
        row["p_gas_co2"] = float(p_gas_co2)
        row["P_gas"] = float(P_gas)
        row["q_gas"] = float(q_gas)
        row["gas_frac_ch4"] = float(frac_ch4)
        row["gas_frac_co2"] = float(frac_co2)
        records.append(row)

    out_df = pd.DataFrame.from_records(records)

    final = out_df.iloc[-1]
    faasr_log(
        f"Steady-state summary at t={final['time']:.1f} d: "
        f"pH={final['pH']:.3f}, q_gas={final['q_gas']:.1f} m3/d, "
        f"CH4={final['gas_frac_ch4'] * 100:.1f}%, CO2={final['gas_frac_co2'] * 100:.1f}%"
    )

    # ------------------------------------------------------------------
    # 8) Write and upload output
    # ------------------------------------------------------------------
    local_out = "adm1_model_output.csv"
    out_df.to_csv(local_out, index=False)

    if not os.path.exists(local_out) or os.path.getsize(local_out) == 0:
        faasr_log("ERROR: model output CSV was not written or is empty")
        raise RuntimeError("Failed to produce adm1_model_output.csv")

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded ADM1 model output to S3 as '{output1}' "
              f"({len(out_df)} rows, {out_df.shape[1]} columns)")
    faasr_log("run_adm1_model: completed successfully")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---