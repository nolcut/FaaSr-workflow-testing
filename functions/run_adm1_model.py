import os
import tempfile
import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "validated_influent.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Validated influent CSV must be present in S3 before running the ADM1 model")
        raise SystemExit(1)
    if "validated_initial.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Validated initial conditions CSV must be present in S3 before running the ADM1 model")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "adm1_simulation_results.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: ADM1 simulation results CSV must be uploaded to S3 after successful ODE integration")
        raise SystemExit(1)
# --- end contract helpers ---


def run_adm1_model(folder: str, input1: str, input2: str, output1: str) -> None:
    """Run the ADM1 anaerobic digestion ODE model (BSM2 implementation).

    Parameters
    ----------
    folder  : S3 folder (remote_folder for FaaSr calls)
    input1  : validated influent CSV filename (remote)
    input2  : validated initial conditions CSV filename (remote)
    output1 : output simulation results CSV filename (remote)
    """

    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    with tempfile.TemporaryDirectory() as tmpdir:
        local_influent = os.path.join(tmpdir, "validated_influent.csv")
        local_initial  = os.path.join(tmpdir, "validated_initial.csv")
        local_output   = os.path.join(tmpdir, "adm1_simulation_results.csv")

        # ------------------------------------------------------------------
        # 1. Download inputs
        # ------------------------------------------------------------------
        faasr_log(f"Downloading influent '{input1}' from folder '{folder}'")
        faasr_get_file(local_file=local_influent, remote_folder=folder, remote_file=input1)

        faasr_log(f"Downloading initial conditions '{input2}' from folder '{folder}'")
        faasr_get_file(local_file=local_initial, remote_folder=folder, remote_file=input2)

        # ------------------------------------------------------------------
        # 2. Parse CSVs
        # ------------------------------------------------------------------
        faasr_log("Parsing influent CSV")
        try:
            df_inf = pd.read_csv(local_influent)
        except Exception as e:
            faasr_log(f"ERROR: failed to parse influent CSV: {e}")
            raise

        faasr_log(f"Influent shape: {df_inf.shape}, columns: {df_inf.columns.tolist()}")

        faasr_log("Parsing initial conditions CSV")
        try:
            df_init = pd.read_csv(local_initial)
        except Exception as e:
            faasr_log(f"ERROR: failed to parse initial conditions CSV: {e}")
            raise

        faasr_log(f"Initial conditions shape: {df_init.shape}")

        # ------------------------------------------------------------------
        # 3. BSM2 ADM1 Parameters (Rosen & Jeppsson 2006)
        # ------------------------------------------------------------------

        # --- Stoichiometric parameters ---
        f_sI_xc = 0.1;   f_xI_xc = 0.2;   f_ch_xc = 0.2
        f_pr_xc = 0.2;   f_li_xc = 0.3
        N_xc    = 0.0376/14.0;  N_I = 0.06/14.0;   N_aa  = 0.007
        N_bac   = 0.08/14.0
        C_xc    = 0.02786; C_sI = 0.03;   C_ch  = 0.0313; C_pr  = 0.03
        C_li    = 0.022;   C_xI = 0.03;   C_su  = 0.0313; C_aa  = 0.03
        C_fa    = 0.0217;  C_bu = 0.025;  C_pro = 0.0268; C_ac  = 0.0313
        C_bac   = 0.0313;  C_va = 0.024;  C_ch4 = 0.0156

        f_fa_li  = 0.95
        f_h2_su  = 0.19;  f_bu_su  = 0.13;  f_pro_su = 0.27;  f_ac_su  = 0.41
        f_h2_aa  = 0.06;  f_va_aa  = 0.23;  f_bu_aa  = 0.26
        f_pro_aa = 0.05;  f_ac_aa  = 0.40
        Y_su  = 0.10;  Y_aa  = 0.08;  Y_fa  = 0.06;  Y_c4  = 0.06
        Y_pro = 0.04;  Y_ac  = 0.05;  Y_h2  = 0.06

        # --- Biochemical kinetic parameters ---
        k_dis    = 0.5
        k_hyd_ch = 10.0;  k_hyd_pr = 10.0;  k_hyd_li = 10.0
        K_S_IN   = 1e-4
        k_m_su   = 30.0;  K_S_su   = 0.5
        k_m_aa   = 50.0;  K_S_aa   = 0.3
        k_m_fa   = 6.0;   K_S_fa   = 0.4;   K_Ih2_fa  = 5e-6
        k_m_c4   = 20.0;  K_S_c4   = 0.2;   K_Ih2_c4  = 1e-5
        k_m_pro  = 13.0;  K_S_pro  = 0.1;   K_Ih2_pro = 3.5e-6
        k_m_ac   = 8.0;   K_S_ac   = 0.15;  K_I_nh3   = 0.0018
        k_m_h2   = 35.0;  K_S_h2   = 7e-6
        k_dec    = 0.02   # uniform decay for all biomass

        # pH inhibition limits
        pH_UL_aa = 5.5;  pH_LL_aa = 4.0
        pH_UL_ac = 7.0;  pH_LL_ac = 6.0
        pH_UL_h2 = 6.0;  pH_LL_h2 = 5.0

        # Acid-base rate coefficients (M^-1 d^-1)
        k_A_B = 1e10

        # Fixed (not T-dependent) acid dissociation constants
        K_a_va  = 10.0**(-4.86)
        K_a_bu  = 10.0**(-4.82)
        K_a_pro = 10.0**(-4.88)
        K_a_ac  = 10.0**(-4.76)

        # Physical parameters
        V_liq = 3400.0;  V_gas = 300.0
        R_gas = 0.083145   # bar M^-1 K^-1
        T_base = 298.15    # K
        P_atm  = 1.013     # bar
        k_p    = 5e4       # m^3 d^-1 bar^-1
        k_La   = 200.0     # d^-1

        # --- IC carbon balance stoichiometric sums (for dS_IC/dt) ---
        s1  = -C_xc + f_sI_xc*C_sI + f_ch_xc*C_ch + f_pr_xc*C_pr + f_li_xc*C_li + f_xI_xc*C_xI
        s2  = -C_ch + C_su
        s3  = -C_pr + C_aa
        s4  = -C_li + (1.0 - f_fa_li)*C_su + f_fa_li*C_fa
        s5  = -C_su  + (1.0-Y_su)*(f_bu_su*C_bu  + f_pro_su*C_pro  + f_ac_su*C_ac)  + Y_su*C_bac
        s6  = -C_aa  + (1.0-Y_aa)*(f_va_aa*C_va  + f_bu_aa*C_bu   + f_pro_aa*C_pro + f_ac_aa*C_ac) + Y_aa*C_bac
        s7  = -C_fa  + (1.0-Y_fa)*0.7*C_ac  + Y_fa*C_bac
        s8  = -C_va  + (1.0-Y_c4)*0.54*C_pro + (1.0-Y_c4)*0.31*C_ac + Y_c4*C_bac
        s9  = -C_bu  + (1.0-Y_c4)*0.8*C_ac   + Y_c4*C_bac
        s10 = -C_pro + (1.0-Y_pro)*0.57*C_ac  + Y_pro*C_bac
        s11 = -C_ac  + (1.0-Y_ac)*C_ch4  + Y_ac*C_bac
        s12 = (1.0-Y_h2)*C_ch4 + Y_h2*C_bac
        s13 = -C_bac + C_xc

        # ------------------------------------------------------------------
        # 4. Helper: temperature-dependent physicochemical parameters
        # ------------------------------------------------------------------
        def compute_temp_params(T_op_K):
            fac = (1.0/T_base - 1.0/T_op_K) / (100.0 * R_gas)
            K_w       = 1e-14 * np.exp(55900.0 * fac)
            K_a_co2   = 10.0**(-6.35)  * np.exp(7646.0  * fac)
            K_a_IN_T  = 10.0**(-9.25)  * np.exp(51965.0 * fac)
            p_h2o     = 0.0313 * np.exp(5290.0 * (1.0/T_base - 1.0/T_op_K))
            K_H_co2   = 0.035   * np.exp(-19410.0 * (1.0/T_base - 1.0/T_op_K) / (100.0*R_gas))
            K_H_ch4   = 0.0014  * np.exp(-14240.0 * (1.0/T_base - 1.0/T_op_K) / (100.0*R_gas))
            K_H_h2    = 7.8e-4  * np.exp(-4180.0  * (1.0/T_base - 1.0/T_op_K) / (100.0*R_gas))
            return K_w, K_a_co2, K_a_IN_T, p_h2o, K_H_co2, K_H_ch4, K_H_h2

        # ------------------------------------------------------------------
        # 5. Algebraic pH solver (charge balance, BSM2 Theta formula)
        # ------------------------------------------------------------------
        def solve_pH_algebraic(S_cat, S_an, S_va_ion, S_bu_ion, S_pro_ion,
                               S_ac_ion, S_hco3_ion, S_IN, S_nh3, K_w):
            """Compute S_H+ from charge balance (BSM2 Theta formula, p.10)."""
            S_nh4 = max(S_IN - S_nh3, 0.0)
            Theta = (S_cat + S_nh4
                     - S_hco3_ion
                     - S_ac_ion  / 64.0
                     - S_pro_ion / 112.0
                     - S_bu_ion  / 160.0
                     - S_va_ion  / 208.0
                     - S_an)
            disc = Theta**2 + 4.0 * K_w
            S_H = -Theta / 2.0 + 0.5 * np.sqrt(max(disc, 0.0))
            return max(S_H, 1e-14)

        # ------------------------------------------------------------------
        # 6. Build influent interpolators
        # ------------------------------------------------------------------
        t_inf = df_inf['time'].values.astype(float)
        t_start = float(t_inf[0])
        t_end   = float(t_inf[-1])
        faasr_log(f"Simulation time: {t_start:.4f} to {t_end:.4f} days ({len(t_inf)} points)")

        INF_COLS = [
            "S_su","S_aa","S_fa","S_va","S_bu","S_pro","S_ac",
            "S_h2","S_ch4","S_IC","S_IN","S_I",
            "X_xc","X_ch","X_pr","X_li",
            "X_su","X_aa","X_fa","X_c4","X_pro","X_ac","X_h2","X_I",
            "S_cation","S_anion",
        ]
        Q_COL = "Q"
        T_COL = "T (C)"

        def _make_interp(col, df, default):
            if col in df.columns:
                vals = df[col].values.astype(float)
                return interp1d(t_inf, vals, kind='linear', bounds_error=False,
                                fill_value=(vals[0], vals[-1]))
            faasr_log(f"WARNING: influent column '{col}' missing; using default {default}")
            return lambda t, _d=default: _d

        inf_interps = {c: _make_interp(c, df_inf, 0.0) for c in INF_COLS}
        q_interp    = _make_interp(Q_COL, df_inf, 170.0)
        T_interp    = _make_interp(T_COL, df_inf, 35.0)

        # ------------------------------------------------------------------
        # 7. Initial conditions (35-state ODE vector)
        # State indices:
        #  0-11 : S_su..S_I       (soluble)
        # 12-23 : X_xc..X_I      (particulate)
        # 24-25 : S_cation,S_anion
        # 26-31 : S_va_ion,S_bu_ion,S_pro_ion,S_ac_ion,S_hco3_ion,S_nh3
        # 32-34 : S_gas_h2,S_gas_ch4,S_gas_co2
        # ------------------------------------------------------------------
        CORE_COLS = [
            "S_su","S_aa","S_fa","S_va","S_bu","S_pro","S_ac",
            "S_h2","S_ch4","S_IC","S_IN","S_I",
            "X_xc","X_ch","X_pr","X_li",
            "X_su","X_aa","X_fa","X_c4","X_pro","X_ac","X_h2","X_I",
            "S_cation","S_anion",
        ]
        ION_ODE_COLS = ["S_va_ion","S_bu_ion","S_pro_ion","S_ac_ion","S_hco3_ion","S_nh3"]
        GAS_ODE_COLS = ["S_gas_h2","S_gas_ch4","S_gas_co2"]

        init_row = df_init.iloc[0]
        y0 = np.array(
            [float(init_row[c]) for c in CORE_COLS]
          + [float(init_row[c]) for c in ION_ODE_COLS]
          + [float(init_row[c]) for c in GAS_ODE_COLS],
            dtype=float
        )
        y0 = np.maximum(y0, 0.0)
        faasr_log(f"Initial state vector: {y0.shape[0]} states")

        # ------------------------------------------------------------------
        # 8. ODE right-hand side
        # ------------------------------------------------------------------
        def adm1_ode(t, y):
            # --- Unpack and clip state ---
            y = np.maximum(y, 0.0)
            S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac = y[0:7]
            S_h2, S_ch4, S_IC, S_IN, S_I               = y[7:12]
            X_xc, X_ch, X_pr, X_li                     = y[12:16]
            X_su, X_aa, X_fa, X_c4, X_pro_bac, X_ac, X_h2_bac, X_I = y[16:24]
            S_cat, S_an                                 = y[24], y[25]
            S_va_ion, S_bu_ion, S_pro_ion, S_ac_ion, S_hco3_ion, S_nh3 = y[26:32]
            S_gas_h2, S_gas_ch4, S_gas_co2              = y[32], y[33], y[34]

            # --- Temperature-dependent parameters ---
            T_C   = float(T_interp(t))
            T_op  = T_C + 273.15
            K_w, K_a_co2, K_a_IN_T, p_h2o, K_H_co2, K_H_ch4, K_H_h2 = compute_temp_params(T_op)

            # --- Algebraic pH ---
            S_H_ion = solve_pH_algebraic(
                S_cat, S_an, S_va_ion, S_bu_ion, S_pro_ion,
                S_ac_ion, S_hco3_ion, S_IN, S_nh3, K_w
            )

            # --- Algebraic derived quantities ---
            S_co2     = max(S_IC - S_hco3_ion, 0.0)
            S_nh4_ion = max(S_IN - S_nh3,      0.0)

            # --- pH inhibition (BSM2: Hill function on S_H+, Expression 3) ---
            pHLim_aa = 10.0 ** (-(pH_UL_aa + pH_LL_aa) / 2.0)
            pHLim_ac = 10.0 ** (-(pH_UL_ac + pH_LL_ac) / 2.0)
            pHLim_h2 = 10.0 ** (-(pH_UL_h2 + pH_LL_h2) / 2.0)
            n_aa = 3.0 / (pH_UL_aa - pH_LL_aa)
            n_ac = 3.0 / (pH_UL_ac - pH_LL_ac)
            n_h2 = 3.0 / (pH_UL_h2 - pH_LL_h2)
            I_pH_aa = (pHLim_aa**n_aa) / (S_H_ion**n_aa + pHLim_aa**n_aa)
            I_pH_ac = (pHLim_ac**n_ac) / (S_H_ion**n_ac + pHLim_ac**n_ac)
            I_pH_h2 = (pHLim_h2**n_h2) / (S_H_ion**n_h2 + pHLim_h2**n_h2)

            # --- Other inhibition terms ---
            I_IN_lim = 1.0 / (1.0 + K_S_IN / max(S_IN, 1e-20))
            I_h2_fa  = 1.0 / (1.0 + S_h2 / K_Ih2_fa)
            I_h2_c4  = 1.0 / (1.0 + S_h2 / K_Ih2_c4)
            I_h2_pro = 1.0 / (1.0 + S_h2 / K_Ih2_pro)
            I_nh3    = 1.0 / (1.0 + S_nh3 / K_I_nh3)

            I5  = I_pH_aa * I_IN_lim
            I6  = I_pH_aa * I_IN_lim
            I7  = I_pH_aa * I_IN_lim * I_h2_fa
            I8  = I_pH_aa * I_IN_lim * I_h2_c4
            I9  = I_pH_aa * I_IN_lim * I_h2_c4
            I10 = I_pH_aa * I_IN_lim * I_h2_pro
            I11 = I_pH_ac * I_IN_lim * I_nh3
            I12 = I_pH_h2 * I_IN_lim

            # --- Biochemical process rates (rho 1-19) ---
            rho1  = k_dis    * X_xc
            rho2  = k_hyd_ch * X_ch
            rho3  = k_hyd_pr * X_pr
            rho4  = k_hyd_li * X_li
            rho5  = k_m_su  * S_su  / (K_S_su  + S_su)  * X_su      * I5
            rho6  = k_m_aa  * S_aa  / (K_S_aa  + S_aa)  * X_aa      * I6
            rho7  = k_m_fa  * S_fa  / (K_S_fa  + S_fa)  * X_fa      * I7
            rho8  = k_m_c4  * S_va  / (K_S_c4  + S_va)  * X_c4      * (S_va / (S_bu + S_va + 1e-6)) * I8
            rho9  = k_m_c4  * S_bu  / (K_S_c4  + S_bu)  * X_c4      * (S_bu / (S_va + S_bu + 1e-6)) * I9
            rho10 = k_m_pro * S_pro / (K_S_pro + S_pro) * X_pro_bac * I10
            rho11 = k_m_ac  * S_ac  / (K_S_ac  + S_ac)  * X_ac      * I11
            rho12 = k_m_h2  * S_h2  / (K_S_h2  + S_h2)  * X_h2_bac * I12
            rho13 = k_dec * X_su
            rho14 = k_dec * X_aa
            rho15 = k_dec * X_fa
            rho16 = k_dec * X_c4
            rho17 = k_dec * X_pro_bac
            rho18 = k_dec * X_ac
            rho19 = k_dec * X_h2_bac
            sum_dec = rho13 + rho14 + rho15 + rho16 + rho17 + rho18 + rho19

            # --- Gas partial pressures and flow (BSM2 overpressure formula) ---
            p_gas_h2  = S_gas_h2  * R_gas * T_op / 16.0
            p_gas_ch4 = S_gas_ch4 * R_gas * T_op / 64.0
            p_gas_co2 = S_gas_co2 * R_gas * T_op
            P_gas = p_gas_h2 + p_gas_ch4 + p_gas_co2 + p_h2o
            q_gas = max(k_p * (P_gas - P_atm) * (P_gas / P_atm), 0.0)

            # --- Liquid-gas transfer rates ---
            rho_T8  = k_La * (S_h2  - 16.0 * K_H_h2  * p_gas_h2)
            rho_T9  = k_La * (S_ch4 - 64.0 * K_H_ch4 * p_gas_ch4)
            rho_T10 = k_La * (S_co2 -        K_H_co2 * p_gas_co2)

            # --- Acid-base rates ---
            rho_A4  = k_A_B * (S_va_ion   * (K_a_va  + S_H_ion) - K_a_va  * S_va)
            rho_A5  = k_A_B * (S_bu_ion   * (K_a_bu  + S_H_ion) - K_a_bu  * S_bu)
            rho_A6  = k_A_B * (S_pro_ion  * (K_a_pro + S_H_ion) - K_a_pro * S_pro)
            rho_A7  = k_A_B * (S_ac_ion   * (K_a_ac  + S_H_ion) - K_a_ac  * S_ac)
            rho_A10 = k_A_B * (S_hco3_ion * (K_a_co2 + S_H_ion) - K_a_co2 * S_IC)
            rho_A11 = k_A_B * (S_nh3      * (K_a_IN_T + S_H_ion) - K_a_IN_T * S_IN)

            # --- Influent at time t ---
            q_in = float(q_interp(t))
            dil  = q_in / V_liq

            S_su_in   = float(inf_interps["S_su"](t))
            S_aa_in   = float(inf_interps["S_aa"](t))
            S_fa_in   = float(inf_interps["S_fa"](t))
            S_va_in   = float(inf_interps["S_va"](t))
            S_bu_in   = float(inf_interps["S_bu"](t))
            S_pro_in  = float(inf_interps["S_pro"](t))
            S_ac_in   = float(inf_interps["S_ac"](t))
            S_h2_in   = float(inf_interps["S_h2"](t))
            S_ch4_in  = float(inf_interps["S_ch4"](t))
            S_IC_in   = float(inf_interps["S_IC"](t))
            S_IN_in   = float(inf_interps["S_IN"](t))
            S_I_in    = float(inf_interps["S_I"](t))
            X_xc_in   = float(inf_interps["X_xc"](t))
            X_ch_in   = float(inf_interps["X_ch"](t))
            X_pr_in   = float(inf_interps["X_pr"](t))
            X_li_in   = float(inf_interps["X_li"](t))
            X_su_in   = float(inf_interps["X_su"](t))
            X_aa_in   = float(inf_interps["X_aa"](t))
            X_fa_in   = float(inf_interps["X_fa"](t))
            X_c4_in   = float(inf_interps["X_c4"](t))
            X_pro_in  = float(inf_interps["X_pro"](t))
            X_ac_in   = float(inf_interps["X_ac"](t))
            X_h2_in   = float(inf_interps["X_h2"](t))
            X_I_in    = float(inf_interps["X_I"](t))
            S_cat_in  = float(inf_interps["S_cation"](t))
            S_an_in   = float(inf_interps["S_anion"](t))

            # --- IC carbon balance sum ---
            sum_C = (s1*rho1  + s2*rho2   + s3*rho3   + s4*rho4
                   + s5*rho5  + s6*rho6   + s7*rho7   + s8*rho8
                   + s9*rho9  + s10*rho10 + s11*rho11 + s12*rho12
                   + s13*sum_dec)

            # ------------------------------------------------------------------
            # Water-phase ODEs (Eqs 1-12 in paper)
            # ------------------------------------------------------------------
            dS_su  = dil*(S_su_in  - S_su)  + rho2 + (1.0-f_fa_li)*rho4 - rho5
            dS_aa  = dil*(S_aa_in  - S_aa)  + rho3 - rho6
            dS_fa  = dil*(S_fa_in  - S_fa)  + f_fa_li*rho4 - rho7
            dS_va  = dil*(S_va_in  - S_va)  + (1.0-Y_aa)*f_va_aa*rho6 - rho8
            dS_bu  = (dil*(S_bu_in  - S_bu)
                      + (1.0-Y_su)*f_bu_su*rho5
                      + (1.0-Y_aa)*f_bu_aa*rho6 - rho9)
            dS_pro = (dil*(S_pro_in - S_pro)
                      + (1.0-Y_su)*f_pro_su*rho5
                      + (1.0-Y_aa)*f_pro_aa*rho6
                      + (1.0-Y_c4)*0.54*rho8 - rho10)
            dS_ac  = (dil*(S_ac_in  - S_ac)
                      + (1.0-Y_su)*f_ac_su*rho5
                      + (1.0-Y_aa)*f_ac_aa*rho6
                      + (1.0-Y_fa)*0.7*rho7
                      + (1.0-Y_c4)*0.31*rho8
                      + (1.0-Y_c4)*0.8*rho9
                      + (1.0-Y_pro)*0.57*rho10 - rho11)
            dS_h2  = (dil*(S_h2_in  - S_h2)
                      + (1.0-Y_su)*f_h2_su*rho5
                      + (1.0-Y_aa)*f_h2_aa*rho6
                      + (1.0-Y_fa)*0.3*rho7
                      + (1.0-Y_c4)*0.15*rho8
                      + (1.0-Y_c4)*0.2*rho9
                      + (1.0-Y_pro)*0.43*rho10 - rho12 - rho_T8)
            dS_ch4 = (dil*(S_ch4_in - S_ch4)
                      + (1.0-Y_ac)*rho11 + (1.0-Y_h2)*rho12 - rho_T9)
            dS_IC  = dil*(S_IC_in   - S_IC)  + sum_C - rho_T10
            dS_IN  = (dil*(S_IN_in  - S_IN)
                      - Y_su*N_bac*rho5
                      + (N_aa - Y_aa*N_bac)*rho6
                      - Y_fa*N_bac*rho7
                      - Y_c4*N_bac*(rho8 + rho9)
                      - Y_pro*N_bac*rho10
                      - Y_ac*N_bac*rho11
                      - Y_h2*N_bac*rho12
                      + (N_bac - N_xc)*sum_dec
                      + (N_xc - f_xI_xc*N_I - f_sI_xc*N_I - f_pr_xc*N_aa)*rho1)
            dS_I   = dil*(S_I_in    - S_I)   + f_sI_xc*rho1

            # ------------------------------------------------------------------
            # Particulate ODEs (Eqs 13-24)
            # ------------------------------------------------------------------
            dX_xc      = dil*(X_xc_in  - X_xc)     - rho1  + sum_dec
            dX_ch      = dil*(X_ch_in  - X_ch)     + f_ch_xc*rho1 - rho2
            dX_pr      = dil*(X_pr_in  - X_pr)     + f_pr_xc*rho1 - rho3
            dX_li      = dil*(X_li_in  - X_li)     + f_li_xc*rho1 - rho4
            dX_su      = dil*(X_su_in  - X_su)     + Y_su*rho5   - rho13
            dX_aa      = dil*(X_aa_in  - X_aa)     + Y_aa*rho6   - rho14
            dX_fa      = dil*(X_fa_in  - X_fa)     + Y_fa*rho7   - rho15
            dX_c4      = dil*(X_c4_in  - X_c4)     + Y_c4*(rho8 + rho9) - rho16
            dX_pro_bac = dil*(X_pro_in - X_pro_bac)+ Y_pro*rho10 - rho17
            dX_ac      = dil*(X_ac_in  - X_ac)     + Y_ac*rho11  - rho18
            dX_h2_bac  = dil*(X_h2_in  - X_h2_bac) + Y_h2*rho12  - rho19
            dX_I       = dil*(X_I_in   - X_I)      + f_xI_xc*rho1

            # ------------------------------------------------------------------
            # Cation/anion ODEs (Eqs 25-26)
            # ------------------------------------------------------------------
            dS_cat = dil*(S_cat_in - S_cat)
            dS_an  = dil*(S_an_in  - S_an)

            # ------------------------------------------------------------------
            # Ion state ODEs (Eqs 27-32)
            # ------------------------------------------------------------------
            dS_va_ion   = -rho_A4
            dS_bu_ion   = -rho_A5
            dS_pro_ion  = -rho_A6
            dS_ac_ion   = -rho_A7
            dS_hco3_ion = -rho_A10
            dS_nh3      = -rho_A11

            # ------------------------------------------------------------------
            # Gas phase ODEs (Eqs 33-35)
            # ------------------------------------------------------------------
            dS_gas_h2  = -S_gas_h2  * q_gas / V_gas + rho_T8  * V_liq / V_gas
            dS_gas_ch4 = -S_gas_ch4 * q_gas / V_gas + rho_T9  * V_liq / V_gas
            dS_gas_co2 = -S_gas_co2 * q_gas / V_gas + rho_T10 * V_liq / V_gas

            return [
                dS_su, dS_aa, dS_fa, dS_va, dS_bu, dS_pro, dS_ac,
                dS_h2, dS_ch4, dS_IC, dS_IN, dS_I,
                dX_xc, dX_ch, dX_pr, dX_li,
                dX_su, dX_aa, dX_fa, dX_c4, dX_pro_bac, dX_ac, dX_h2_bac, dX_I,
                dS_cat, dS_an,
                dS_va_ion, dS_bu_ion, dS_pro_ion, dS_ac_ion, dS_hco3_ion, dS_nh3,
                dS_gas_h2, dS_gas_ch4, dS_gas_co2,
            ]

        # ------------------------------------------------------------------
        # 9. Integrate ODE system
        # ------------------------------------------------------------------
        faasr_log(f"Starting ADM1 ODE integration (Radau stiff solver)")
        sol = solve_ivp(
            adm1_ode,
            [t_start, t_end],
            y0,
            method='Radau',
            t_eval=t_inf,
            rtol=1e-6,
            atol=1e-8,
            dense_output=False,
            max_step=0.5 / 24.0,   # max 30-minute internal step
        )

        if not sol.success:
            msg = f"ADM1 ODE integration failed: {sol.message}"
            faasr_log(f"ERROR: {msg}")
            raise RuntimeError(msg)

        faasr_log(f"ODE integration complete: {sol.t.shape[0]} output time points")

        # ------------------------------------------------------------------
        # 10. Compute algebraic outputs at each time point
        # ------------------------------------------------------------------
        Y     = sol.y          # shape (35, n_t)
        t_out = sol.t
        n_t   = len(t_out)

        pH_arr        = np.zeros(n_t)
        S_H_ion_arr   = np.zeros(n_t)
        S_co2_arr     = np.zeros(n_t)
        S_nh4_arr     = np.zeros(n_t)
        q_gas_arr     = np.zeros(n_t)
        p_gas_h2_arr  = np.zeros(n_t)
        p_gas_ch4_arr = np.zeros(n_t)
        p_gas_co2_arr = np.zeros(n_t)

        for i in range(n_t):
            T_C  = float(T_interp(t_out[i]))
            T_op = T_C + 273.15
            K_w, K_a_co2, K_a_IN_T, p_h2o, K_H_co2, K_H_ch4, K_H_h2 = compute_temp_params(T_op)

            yi = np.maximum(Y[:, i], 0.0)
            S_cat    = yi[24]; S_an     = yi[25]
            S_va_ion = yi[26]; S_bu_ion = yi[27]
            S_pro_ion= yi[28]; S_ac_ion = yi[29]
            S_hco3   = yi[30]; S_nh3    = yi[31]
            S_IC     = yi[9];  S_IN     = yi[10]
            S_gas_h2 = yi[32]; S_gas_ch4= yi[33]; S_gas_co2= yi[34]

            S_H = solve_pH_algebraic(S_cat, S_an, S_va_ion, S_bu_ion, S_pro_ion,
                                     S_ac_ion, S_hco3, S_IN, S_nh3, K_w)
            S_H_ion_arr[i] = S_H
            pH_arr[i]      = -np.log10(S_H)
            S_co2_arr[i]   = max(S_IC - S_hco3, 0.0)
            S_nh4_arr[i]   = max(S_IN - S_nh3,  0.0)

            p_h2  = S_gas_h2  * R_gas * T_op / 16.0
            p_ch4 = S_gas_ch4 * R_gas * T_op / 64.0
            p_co2 = S_gas_co2 * R_gas * T_op
            P_gas = p_h2 + p_ch4 + p_co2 + p_h2o
            q_gas = max(k_p * (P_gas - P_atm) * (P_gas / P_atm), 0.0)

            q_gas_arr[i]      = q_gas
            p_gas_h2_arr[i]   = p_h2
            p_gas_ch4_arr[i]  = p_ch4
            p_gas_co2_arr[i]  = p_co2

        # ------------------------------------------------------------------
        # 11. Assemble output DataFrame
        # ------------------------------------------------------------------
        data = {"time": t_out}
        for j, col in enumerate(CORE_COLS):
            data[col] = Y[j, :]
        data["S_H_ion"]    = S_H_ion_arr
        for j, col in enumerate(ION_ODE_COLS):
            data[col] = Y[26 + j, :]
        data["S_co2"]      = S_co2_arr
        data["S_nh4_ion"]  = S_nh4_arr
        data["S_gas_h2"]   = Y[32, :]
        data["S_gas_ch4"]  = Y[33, :]
        data["S_gas_co2"]  = Y[34, :]
        data["pH"]         = pH_arr
        data["q_gas"]      = q_gas_arr
        data["p_gas_h2"]   = p_gas_h2_arr
        data["p_gas_ch4"]  = p_gas_ch4_arr
        data["p_gas_co2"]  = p_gas_co2_arr

        df_out = pd.DataFrame(data)
        faasr_log(f"Output DataFrame: {df_out.shape[0]} rows x {df_out.shape[1]} columns")

        # ------------------------------------------------------------------
        # 12. Save and upload
        # ------------------------------------------------------------------
        df_out.to_csv(local_output, index=False)
        faasr_log(f"Uploading '{output1}' to folder '{folder}'")
        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
        faasr_log("run_adm1_model complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---