import numpy as np
import scipy.integrate
import pandas as pd
import tempfile
import os


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "digester_influent.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Influent time-series CSV must be present in S3 before running ADM1 simulation")
        raise SystemExit(1)
    if "digester_initial.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Initial reactor state CSV must be present in S3 before running ADM1 simulation")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "dynamic_out.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: ADM1 simulation output CSV with 38 state variable trajectories must be written to S3")
        raise SystemExit(1)
# --- end contract helpers ---


def pyadm1(folder: str, input1: str, input2: str, output1: str) -> None:
    """Run the ADM1 anaerobic digestion model (BSM2 / Rosen et al. 2006).

    Reads influent time-series and initial reactor state from S3, integrates
    the ADM1 ODE/DAE system over the supplied time steps, and writes all 38
    state variable trajectories to the output CSV.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("pyadm1: starting ADM1 simulation")

    with tempfile.TemporaryDirectory() as tmpdir:
        influent_path = os.path.join(tmpdir, "influent.csv")
        initial_path  = os.path.join(tmpdir, "initial.csv")
        output_path   = os.path.join(tmpdir, "dynamic_out.csv")

        faasr_get_file(local_file=influent_path, remote_folder=folder, remote_file=input1)
        faasr_get_file(local_file=initial_path,  remote_folder=folder, remote_file=input2)

        influent_state = pd.read_csv(influent_path)
        initial_state  = pd.read_csv(initial_path)

        faasr_log(f"pyadm1: loaded influent ({len(influent_state)} rows) and initial state")

        # ------------------------------------------------------------------ #
        # Constants (BSM2 / Rosen et al. 2006)                               #
        # ------------------------------------------------------------------ #
        R       = 0.083145   # bar.M^-1.K^-1
        T_base  = 298.15     # K
        p_atm   = 1.013      # bar
        T_op    = 308.15     # K

        # Stoichiometric parameters
        f_sI_xc = 0.1;  f_xI_xc = 0.2;  f_ch_xc = 0.2;  f_pr_xc = 0.2;  f_li_xc = 0.3
        N_xc = 0.0376 / 14;  N_I = 0.06 / 14;  N_aa = 0.007;  N_bac = 0.08 / 14
        C_xc = 0.02786;  C_sI = 0.03;  C_ch = 0.0313;  C_pr = 0.03;  C_li = 0.022
        C_xI = 0.03;  C_su = 0.0313;  C_aa = 0.03;  C_fa = 0.0217
        C_bu = 0.025;  C_pro = 0.0268;  C_ac = 0.0313;  C_bac = 0.0313;  C_va = 0.024
        C_ch4 = 0.0156
        f_fa_li = 0.95;  f_h2_su = 0.19;  f_bu_su = 0.13;  f_pro_su = 0.27;  f_ac_su = 0.41
        Y_su = 0.1;  f_h2_aa = 0.06;  f_va_aa = 0.23;  f_bu_aa = 0.26
        f_pro_aa = 0.05;  f_ac_aa = 0.40
        Y_aa = 0.08;  Y_fa = 0.06;  Y_c4 = 0.06;  Y_pro = 0.04;  Y_ac = 0.05;  Y_h2 = 0.06

        # Biochemical parameters
        k_dis   = 0.5;  k_hyd_ch = 10;  k_hyd_pr = 10;  k_hyd_li = 10
        K_S_IN  = 1e-4
        k_m_su  = 30;  K_S_su  = 0.5;  pH_UL_aa = 5.5;  pH_LL_aa = 4.0
        k_m_aa  = 50;  K_S_aa  = 0.3
        k_m_fa  = 6;   K_S_fa  = 0.4;  K_I_h2_fa  = 5e-6
        k_m_c4  = 20;  K_S_c4  = 0.2;  K_I_h2_c4  = 1e-5
        k_m_pro = 13;  K_S_pro = 0.1;  K_I_h2_pro = 3.5e-6
        k_m_ac  = 8;   K_S_ac  = 0.15; K_I_nh3    = 0.0018
        pH_UL_ac = 7.0; pH_LL_ac = 6.0
        k_m_h2  = 35;  K_S_h2  = 7e-6
        pH_UL_h2 = 6.0; pH_LL_h2 = 5.0
        k_dec_X_su  = 0.02;  k_dec_X_aa  = 0.02;  k_dec_X_fa  = 0.02
        k_dec_X_c4  = 0.02;  k_dec_X_pro = 0.02;  k_dec_X_ac  = 0.02;  k_dec_X_h2 = 0.02

        # Physico-chemical parameters
        T_ad = 308.15
        K_w     = 1e-14 * np.exp((55900  / (100 * R)) * (1 / T_base - 1 / T_ad))
        K_a_va  = 10 ** -4.86
        K_a_bu  = 10 ** -4.82
        K_a_pro = 10 ** -4.88
        K_a_ac  = 10 ** -4.76
        K_a_co2 = 10 ** -6.35 * np.exp((7646  / (100 * R)) * (1 / T_base - 1 / T_ad))
        K_a_IN  = 10 ** -9.25 * np.exp((51965 / (100 * R)) * (1 / T_base - 1 / T_ad))
        k_A_B_va  = 1e10;  k_A_B_bu  = 1e10;  k_A_B_pro = 1e10;  k_A_B_ac  = 1e10
        k_A_B_co2 = 1e10;  k_A_B_IN  = 1e10
        p_gas_h2o = 0.0313 * np.exp(5290 * (1 / T_base - 1 / T_ad))
        k_p   = 5e4
        k_L_a = 200.0
        K_H_co2 = 0.035  * np.exp((-19410 / (100 * R)) * (1 / T_base - 1 / T_ad))
        K_H_ch4 = 0.0014 * np.exp((-14240 / (100 * R)) * (1 / T_base - 1 / T_ad))
        K_H_h2  = 7.8e-4 * np.exp(-4180  / (100 * R) * (1 / T_base - 1 / T_ad))

        # Physical parameters
        V_liq = 3400.0;  V_gas = 300.0

        # pH inhibition constants
        K_pH_aa = 10 ** (-1 * (pH_LL_aa + pH_UL_aa) / 2.0)
        nn_aa   = 3.0 / (pH_UL_aa - pH_LL_aa)
        K_pH_ac = 10 ** (-1 * (pH_LL_ac + pH_UL_ac) / 2.0)
        n_ac    = 3.0 / (pH_UL_ac - pH_LL_ac)
        K_pH_h2 = 10 ** (-1 * (pH_LL_h2 + pH_UL_h2) / 2.0)
        n_h2    = 3.0 / (pH_UL_h2 - pH_LL_h2)

        # ------------------------------------------------------------------ #
        # Read initial reactor state                                           #
        # ------------------------------------------------------------------ #
        S_su  = initial_state['S_su'][0]
        S_aa  = initial_state['S_aa'][0]
        S_fa  = initial_state['S_fa'][0]
        S_va  = initial_state['S_va'][0]
        S_bu  = initial_state['S_bu'][0]
        S_pro = initial_state['S_pro'][0]
        S_ac  = initial_state['S_ac'][0]
        S_h2  = initial_state['S_h2'][0]
        S_ch4 = initial_state['S_ch4'][0]
        S_IC  = initial_state['S_IC'][0]
        S_IN  = initial_state['S_IN'][0]
        S_I   = initial_state['S_I'][0]
        X_xc  = initial_state['X_xc'][0]
        X_ch  = initial_state['X_ch'][0]
        X_pr  = initial_state['X_pr'][0]
        X_li  = initial_state['X_li'][0]
        X_su  = initial_state['X_su'][0]
        X_aa  = initial_state['X_aa'][0]
        X_fa  = initial_state['X_fa'][0]
        X_c4  = initial_state['X_c4'][0]
        X_pro = initial_state['X_pro'][0]
        X_ac  = initial_state['X_ac'][0]
        X_h2  = initial_state['X_h2'][0]
        X_I   = initial_state['X_I'][0]
        S_cation = initial_state['S_cation'][0]
        S_anion  = initial_state['S_anion'][0]
        S_H_ion  = initial_state['S_H_ion'][0]
        S_va_ion = initial_state['S_va_ion'][0]
        S_bu_ion = initial_state['S_bu_ion'][0]
        S_pro_ion= initial_state['S_pro_ion'][0]
        S_ac_ion = initial_state['S_ac_ion'][0]
        S_hco3_ion = initial_state['S_hco3_ion'][0]
        S_nh3    = initial_state['S_nh3'][0]
        S_nh4_ion = 0.0041   # initial value from Rosen et al. (2006) BSM2 report
        S_co2    = 0.14      # initial value from Rosen et al. (2006) BSM2 report
        S_gas_h2  = initial_state['S_gas_h2'][0]
        S_gas_ch4 = initial_state['S_gas_ch4'][0]
        S_gas_co2 = initial_state['S_gas_co2'][0]

        q_ad = 178.4674   # m^3.d^-1

        # ------------------------------------------------------------------ #
        # Helper: build influent vector for time step i                       #
        # ------------------------------------------------------------------ #
        def get_influent(i):
            return [
                influent_state['S_su'][i],
                influent_state['S_aa'][i],
                influent_state['S_fa'][i],
                influent_state['S_va'][i],
                influent_state['S_bu'][i],
                influent_state['S_pro'][i],
                influent_state['S_ac'][i],
                influent_state['S_h2'][i],
                influent_state['S_ch4'][i],
                influent_state['S_IC'][i],
                influent_state['S_IN'][i],
                influent_state['S_I'][i],
                influent_state['X_xc'][i],
                influent_state['X_ch'][i],
                influent_state['X_pr'][i],
                influent_state['X_li'][i],
                influent_state['X_su'][i],
                influent_state['X_aa'][i],
                influent_state['X_fa'][i],
                influent_state['X_c4'][i],
                influent_state['X_pro'][i],
                influent_state['X_ac'][i],
                influent_state['X_h2'][i],
                influent_state['X_I'][i],
                influent_state['S_cation'][i],
                influent_state['S_anion'][i],
            ]

        # state_input is a mutable 1-element wrapper so ADM1_ODE closure sees updates
        state_input_ref = [get_influent(0)]

        # ------------------------------------------------------------------ #
        # ADM1 ODE function (Rosen et al. 2006 BSM2)                         #
        # ------------------------------------------------------------------ #
        def ADM1_ODE(t, sv):
            (sv_S_su, sv_S_aa, sv_S_fa, sv_S_va, sv_S_bu, sv_S_pro, sv_S_ac,
             sv_S_h2, sv_S_ch4, sv_S_IC, sv_S_IN, sv_S_I,
             sv_X_xc, sv_X_ch, sv_X_pr, sv_X_li,
             sv_X_su, sv_X_aa, sv_X_fa, sv_X_c4, sv_X_pro, sv_X_ac, sv_X_h2, sv_X_I,
             sv_S_cation, sv_S_anion,
             sv_S_H_ion,
             sv_S_va_ion, sv_S_bu_ion, sv_S_pro_ion, sv_S_ac_ion, sv_S_hco3_ion,
             sv_S_co2, sv_S_nh3, sv_S_nh4_ion,
             sv_S_gas_h2, sv_S_gas_ch4, sv_S_gas_co2) = sv

            si = state_input_ref[0]
            (si_S_su, si_S_aa, si_S_fa, si_S_va, si_S_bu, si_S_pro, si_S_ac,
             si_S_h2, si_S_ch4, si_S_IC, si_S_IN, si_S_I,
             si_X_xc, si_X_ch, si_X_pr, si_X_li,
             si_X_su, si_X_aa, si_X_fa, si_X_c4, si_X_pro, si_X_ac, si_X_h2, si_X_I,
             si_S_cation, si_S_anion) = si

            sv_S_nh4_ion = sv_S_IN  - sv_S_nh3
            sv_S_co2     = sv_S_IC  - sv_S_hco3_ion

            I_pH_aa = (K_pH_aa ** nn_aa) / (sv_S_H_ion ** nn_aa + K_pH_aa ** nn_aa)
            I_pH_ac = (K_pH_ac ** n_ac)  / (sv_S_H_ion ** n_ac  + K_pH_ac ** n_ac)
            I_pH_h2 = (K_pH_h2 ** n_h2)  / (sv_S_H_ion ** n_h2  + K_pH_h2 ** n_h2)
            I_IN_lim = 1.0 / (1.0 + K_S_IN  / sv_S_IN)
            I_h2_fa  = 1.0 / (1.0 + sv_S_h2 / K_I_h2_fa)
            I_h2_c4  = 1.0 / (1.0 + sv_S_h2 / K_I_h2_c4)
            I_h2_pro = 1.0 / (1.0 + sv_S_h2 / K_I_h2_pro)
            I_nh3    = 1.0 / (1.0 + sv_S_nh3 / K_I_nh3)

            I_5  = I_pH_aa * I_IN_lim
            I_6  = I_5
            I_7  = I_pH_aa * I_IN_lim * I_h2_fa
            I_8  = I_pH_aa * I_IN_lim * I_h2_c4
            I_9  = I_8
            I_10 = I_pH_aa * I_IN_lim * I_h2_pro
            I_11 = I_pH_ac * I_IN_lim * I_nh3
            I_12 = I_pH_h2 * I_IN_lim

            Rho_1  = k_dis    * sv_X_xc
            Rho_2  = k_hyd_ch * sv_X_ch
            Rho_3  = k_hyd_pr * sv_X_pr
            Rho_4  = k_hyd_li * sv_X_li
            Rho_5  = k_m_su  * sv_S_su  / (K_S_su  + sv_S_su)  * sv_X_su  * I_5
            Rho_6  = k_m_aa  * sv_S_aa  / (K_S_aa  + sv_S_aa)  * sv_X_aa  * I_6
            Rho_7  = k_m_fa  * sv_S_fa  / (K_S_fa  + sv_S_fa)  * sv_X_fa  * I_7
            Rho_8  = k_m_c4  * sv_S_va  / (K_S_c4  + sv_S_va)  * sv_X_c4  * (sv_S_va / (sv_S_bu + sv_S_va + 1e-6)) * I_8
            Rho_9  = k_m_c4  * sv_S_bu  / (K_S_c4  + sv_S_bu)  * sv_X_c4  * (sv_S_bu / (sv_S_bu + sv_S_va + 1e-6)) * I_9
            Rho_10 = k_m_pro * sv_S_pro / (K_S_pro + sv_S_pro) * sv_X_pro * I_10
            Rho_11 = k_m_ac  * sv_S_ac  / (K_S_ac  + sv_S_ac)  * sv_X_ac  * I_11
            Rho_12 = k_m_h2  * sv_S_h2  / (K_S_h2  + sv_S_h2)  * sv_X_h2  * I_12
            Rho_13 = k_dec_X_su  * sv_X_su
            Rho_14 = k_dec_X_aa  * sv_X_aa
            Rho_15 = k_dec_X_fa  * sv_X_fa
            Rho_16 = k_dec_X_c4  * sv_X_c4
            Rho_17 = k_dec_X_pro * sv_X_pro
            Rho_18 = k_dec_X_ac  * sv_X_ac
            Rho_19 = k_dec_X_h2  * sv_X_h2

            # gas phase
            p_gas_h2_  = sv_S_gas_h2  * R * T_op / 16
            p_gas_ch4_ = sv_S_gas_ch4 * R * T_op / 64
            p_gas_co2_ = sv_S_gas_co2 * R * T_op
            p_gas_     = p_gas_h2_ + p_gas_ch4_ + p_gas_co2_ + p_gas_h2o
            q_gas_     = k_p * (p_gas_ - p_atm)
            if q_gas_ < 0:
                q_gas_ = 0.0

            Rho_T_8  = k_L_a * (sv_S_h2  - 16  * K_H_h2  * p_gas_h2_)
            Rho_T_9  = k_L_a * (sv_S_ch4 - 64  * K_H_ch4 * p_gas_ch4_)
            Rho_T_10 = k_L_a * (sv_S_co2 - K_H_co2 * p_gas_co2_)

            # differential equations 1-12 (soluble)
            diff_S_su  = q_ad / V_liq * (si_S_su  - sv_S_su)  + Rho_2 + (1 - f_fa_li) * Rho_4 - Rho_5
            diff_S_aa  = q_ad / V_liq * (si_S_aa  - sv_S_aa)  + Rho_3 - Rho_6
            diff_S_fa  = q_ad / V_liq * (si_S_fa  - sv_S_fa)  + f_fa_li * Rho_4 - Rho_7
            diff_S_va  = q_ad / V_liq * (si_S_va  - sv_S_va)  + (1 - Y_aa) * f_va_aa * Rho_6 - Rho_8
            diff_S_bu  = q_ad / V_liq * (si_S_bu  - sv_S_bu)  + (1 - Y_su) * f_bu_su * Rho_5 + (1 - Y_aa) * f_bu_aa * Rho_6 - Rho_9
            diff_S_pro = q_ad / V_liq * (si_S_pro - sv_S_pro) + (1 - Y_su) * f_pro_su * Rho_5 + (1 - Y_aa) * f_pro_aa * Rho_6 + (1 - Y_c4) * 0.54 * Rho_8 - Rho_10
            diff_S_ac  = (q_ad / V_liq * (si_S_ac - sv_S_ac)
                         + (1 - Y_su) * f_ac_su * Rho_5 + (1 - Y_aa) * f_ac_aa * Rho_6
                         + (1 - Y_fa) * 0.7 * Rho_7
                         + (1 - Y_c4) * 0.31 * Rho_8 + (1 - Y_c4) * 0.8 * Rho_9
                         + (1 - Y_pro) * 0.57 * Rho_10 - Rho_11)
            diff_S_h2  = 0.0   # handled by DAE

            diff_S_ch4 = q_ad / V_liq * (si_S_ch4 - sv_S_ch4) + (1 - Y_ac) * Rho_11 + (1 - Y_h2) * Rho_12 - Rho_T_9

            s_1  = -C_xc + f_sI_xc * C_sI + f_ch_xc * C_ch + f_pr_xc * C_pr + f_li_xc * C_li + f_xI_xc * C_xI
            s_2  = -C_ch + C_su
            s_3  = -C_pr + C_aa
            s_4  = -C_li + (1 - f_fa_li) * C_su + f_fa_li * C_fa
            s_5  = -C_su + (1 - Y_su) * (f_bu_su * C_bu + f_pro_su * C_pro + f_ac_su * C_ac) + Y_su * C_bac
            s_6  = -C_aa + (1 - Y_aa) * (f_va_aa * C_va + f_bu_aa * C_bu + f_pro_aa * C_pro + f_ac_aa * C_ac) + Y_aa * C_bac
            s_7  = -C_fa + (1 - Y_fa) * 0.7 * C_ac + Y_fa * C_bac
            s_8  = -C_va + (1 - Y_c4) * 0.54 * C_pro + (1 - Y_c4) * 0.31 * C_ac + Y_c4 * C_bac
            s_9  = -C_bu + (1 - Y_c4) * 0.8 * C_ac + Y_c4 * C_bac
            s_10 = -C_pro + (1 - Y_pro) * 0.57 * C_ac + Y_pro * C_bac
            s_11 = -C_ac + (1 - Y_ac) * C_ch4 + Y_ac * C_bac
            s_12 = (1 - Y_h2) * C_ch4 + Y_h2 * C_bac
            s_13 = -C_bac + C_xc

            Sigma = (s_1 * Rho_1 + s_2 * Rho_2 + s_3 * Rho_3 + s_4 * Rho_4
                     + s_5 * Rho_5 + s_6 * Rho_6 + s_7 * Rho_7 + s_8 * Rho_8
                     + s_9 * Rho_9 + s_10 * Rho_10 + s_11 * Rho_11 + s_12 * Rho_12
                     + s_13 * (Rho_13 + Rho_14 + Rho_15 + Rho_16 + Rho_17 + Rho_18 + Rho_19))

            diff_S_IC = q_ad / V_liq * (si_S_IC - sv_S_IC) - Sigma - Rho_T_10
            diff_S_IN = (q_ad / V_liq * (si_S_IN - sv_S_IN)
                        + (N_xc - f_xI_xc * N_I - f_sI_xc * N_I - f_pr_xc * N_aa) * Rho_1
                        - Y_su * N_bac * Rho_5 + (N_aa - Y_aa * N_bac) * Rho_6
                        - Y_fa * N_bac * Rho_7 - Y_c4 * N_bac * Rho_8 - Y_c4 * N_bac * Rho_9
                        - Y_pro * N_bac * Rho_10 - Y_ac * N_bac * Rho_11 - Y_h2 * N_bac * Rho_12
                        + (N_bac - N_xc) * (Rho_13 + Rho_14 + Rho_15 + Rho_16 + Rho_17 + Rho_18 + Rho_19))
            diff_S_I = q_ad / V_liq * (si_S_I - sv_S_I) + f_sI_xc * Rho_1

            # differential equations 13-24 (particulate)
            diff_X_xc  = q_ad / V_liq * (si_X_xc - sv_X_xc) - Rho_1 + (Rho_13 + Rho_14 + Rho_15 + Rho_16 + Rho_17 + Rho_18 + Rho_19)
            diff_X_ch  = q_ad / V_liq * (si_X_ch  - sv_X_ch)  + f_ch_xc * Rho_1 - Rho_2
            diff_X_pr  = q_ad / V_liq * (si_X_pr  - sv_X_pr)  + f_pr_xc * Rho_1 - Rho_3
            diff_X_li  = q_ad / V_liq * (si_X_li  - sv_X_li)  + f_li_xc * Rho_1 - Rho_4
            diff_X_su  = q_ad / V_liq * (si_X_su  - sv_X_su)  + Y_su  * Rho_5  - Rho_13
            diff_X_aa  = q_ad / V_liq * (si_X_aa  - sv_X_aa)  + Y_aa  * Rho_6  - Rho_14
            diff_X_fa  = q_ad / V_liq * (si_X_fa  - sv_X_fa)  + Y_fa  * Rho_7  - Rho_15
            diff_X_c4  = q_ad / V_liq * (si_X_c4  - sv_X_c4)  + Y_c4  * (Rho_8 + Rho_9) - Rho_16
            diff_X_pro = q_ad / V_liq * (si_X_pro - sv_X_pro) + Y_pro * Rho_10 - Rho_17
            diff_X_ac  = q_ad / V_liq * (si_X_ac  - sv_X_ac)  + Y_ac  * Rho_11 - Rho_18
            diff_X_h2  = q_ad / V_liq * (si_X_h2  - sv_X_h2)  + Y_h2  * Rho_12 - Rho_19
            diff_X_I   = q_ad / V_liq * (si_X_I   - sv_X_I)   + f_xI_xc * Rho_1

            # differential equations 25-26 (ions)
            diff_S_cation = q_ad / V_liq * (si_S_cation - sv_S_cation)
            diff_S_anion  = q_ad / V_liq * (si_S_anion  - sv_S_anion)

            # DAE states: derivatives set to 0 (solved algebraically)
            diff_S_H_ion    = 0.0
            diff_S_va_ion   = 0.0
            diff_S_bu_ion   = 0.0
            diff_S_pro_ion  = 0.0
            diff_S_ac_ion   = 0.0
            diff_S_hco3_ion = 0.0
            diff_S_co2      = 0.0
            diff_S_nh3      = 0.0
            diff_S_nh4_ion  = 0.0

            # gas phase equations
            diff_S_gas_h2  = (-q_gas_ / V_gas * sv_S_gas_h2)  + Rho_T_8  * V_liq / V_gas
            diff_S_gas_ch4 = (-q_gas_ / V_gas * sv_S_gas_ch4) + Rho_T_9  * V_liq / V_gas
            diff_S_gas_co2 = (-q_gas_ / V_gas * sv_S_gas_co2) + Rho_T_10 * V_liq / V_gas

            return (diff_S_su, diff_S_aa, diff_S_fa, diff_S_va, diff_S_bu, diff_S_pro, diff_S_ac,
                    diff_S_h2, diff_S_ch4, diff_S_IC, diff_S_IN, diff_S_I,
                    diff_X_xc, diff_X_ch, diff_X_pr, diff_X_li,
                    diff_X_su, diff_X_aa, diff_X_fa, diff_X_c4, diff_X_pro, diff_X_ac, diff_X_h2, diff_X_I,
                    diff_S_cation, diff_S_anion,
                    diff_S_H_ion,
                    diff_S_va_ion, diff_S_bu_ion, diff_S_pro_ion, diff_S_ac_ion, diff_S_hco3_ion,
                    diff_S_co2, diff_S_nh3, diff_S_nh4_ion,
                    diff_S_gas_h2, diff_S_gas_ch4, diff_S_gas_co2)

        # ------------------------------------------------------------------ #
        # DAE solver (Newton-Raphson, Rosen et al. 2006)                      #
        # Returns updated (S_H_ion, pH, S_h2, S_va_ion, S_bu_ion,            #
        #                  S_pro_ion, S_ac_ion, S_hco3_ion, S_nh3)           #
        # ------------------------------------------------------------------ #
        def DAESolve(S_va, S_bu, S_pro, S_ac, S_IC, S_IN, S_cation, S_anion,
                     S_h2, S_gas_h2, S_su, S_aa, S_fa,
                     X_su, X_aa, X_fa, X_c4, X_pro, X_h2,
                     S_H_ion_init):
            eps    = 1e-7
            tol    = 1e-12
            maxIter = 1000

            # --- Newton-Raphson for S_H_ion ---
            S_H_ion = S_H_ion_init
            shdelta = 1.0
            i = 1
            while (abs(shdelta) > tol) and (i <= maxIter):
                S_va_ion_   = K_a_va  * S_va  / (K_a_va  + S_H_ion)
                S_bu_ion_   = K_a_bu  * S_bu  / (K_a_bu  + S_H_ion)
                S_pro_ion_  = K_a_pro * S_pro / (K_a_pro + S_H_ion)
                S_ac_ion_   = K_a_ac  * S_ac  / (K_a_ac  + S_H_ion)
                S_hco3_ion_ = K_a_co2 * S_IC  / (K_a_co2 + S_H_ion)
                S_nh3_      = K_a_IN  * S_IN  / (K_a_IN  + S_H_ion)
                shdelta = (S_cation + (S_IN - S_nh3_) + S_H_ion
                           - S_hco3_ion_
                           - S_ac_ion_  / 64.0
                           - S_pro_ion_ / 112.0
                           - S_bu_ion_  / 160.0
                           - S_va_ion_  / 208.0
                           - K_w / S_H_ion - S_anion)
                shgradeq = (1
                            + K_a_IN  * S_IN  / ((K_a_IN  + S_H_ion) ** 2)
                            + K_a_co2 * S_IC  / ((K_a_co2 + S_H_ion) ** 2)
                            + (1 / 64.0)  * K_a_ac  * S_ac  / ((K_a_ac  + S_H_ion) ** 2)
                            + (1 / 112.0) * K_a_pro * S_pro / ((K_a_pro + S_H_ion) ** 2)
                            + (1 / 160.0) * K_a_bu  * S_bu  / ((K_a_bu  + S_H_ion) ** 2)
                            + (1 / 208.0) * K_a_va  * S_va  / ((K_a_va  + S_H_ion) ** 2)
                            + K_w / (S_H_ion ** 2))
                S_H_ion = S_H_ion - shdelta / shgradeq
                if S_H_ion <= 0:
                    S_H_ion = tol
                i += 1

            pH_new = -np.log10(S_H_ion)

            # Final ion values at converged S_H_ion
            S_va_ion_f   = K_a_va  * S_va  / (K_a_va  + S_H_ion)
            S_bu_ion_f   = K_a_bu  * S_bu  / (K_a_bu  + S_H_ion)
            S_pro_ion_f  = K_a_pro * S_pro / (K_a_pro + S_H_ion)
            S_ac_ion_f   = K_a_ac  * S_ac  / (K_a_ac  + S_H_ion)
            S_hco3_ion_f = K_a_co2 * S_IC  / (K_a_co2 + S_H_ion)
            S_nh3_f      = K_a_IN  * S_IN  / (K_a_IN  + S_H_ion)

            # --- Newton-Raphson for S_h2 ---
            prevS_H_ion = S_H_ion_init   # matches original: uses pre-update S_H_ion
            S_h2_new = S_h2
            S_h2delta = 1.0
            j = 1
            while (abs(S_h2delta) > tol) and (j <= maxIter):
                I_pH_aa_d = (K_pH_aa ** nn_aa) / (prevS_H_ion ** nn_aa + K_pH_aa ** nn_aa)
                I_pH_h2_d = (K_pH_h2 ** n_h2)  / (prevS_H_ion ** n_h2  + K_pH_h2 ** n_h2)
                I_IN_lim_d = 1.0 / (1.0 + K_S_IN  / S_IN)
                I_h2_fa_d  = 1.0 / (1.0 + S_h2_new / K_I_h2_fa)
                I_h2_c4_d  = 1.0 / (1.0 + S_h2_new / K_I_h2_c4)
                I_h2_pro_d = 1.0 / (1.0 + S_h2_new / K_I_h2_pro)

                I_5_d  = I_pH_aa_d * I_IN_lim_d
                I_6_d  = I_5_d
                I_7_d  = I_pH_aa_d * I_IN_lim_d * I_h2_fa_d
                I_8_d  = I_pH_aa_d * I_IN_lim_d * I_h2_c4_d
                I_9_d  = I_8_d
                I_10_d = I_pH_aa_d * I_IN_lim_d * I_h2_pro_d
                I_12_d = I_pH_h2_d * I_IN_lim_d

                si = state_input_ref[0]
                si_S_h2 = si[7]

                Rho_5_d  = k_m_su  * S_su  / (K_S_su  + S_su)  * X_su  * I_5_d
                Rho_6_d  = k_m_aa  * S_aa  / (K_S_aa  + S_aa)  * X_aa  * I_6_d
                Rho_7_d  = k_m_fa  * S_fa  / (K_S_fa  + S_fa)  * X_fa  * I_7_d
                Rho_8_d  = k_m_c4  * S_va  / (K_S_c4  + S_va)  * X_c4  * (S_va / (S_bu + S_va + 1e-6)) * I_8_d
                Rho_9_d  = k_m_c4  * S_bu  / (K_S_c4  + S_bu)  * X_c4  * (S_bu / (S_bu + S_va + 1e-6)) * I_9_d
                Rho_10_d = k_m_pro * S_pro / (K_S_pro + S_pro) * X_pro * I_10_d
                Rho_12_d = k_m_h2  * S_h2_new / (K_S_h2 + S_h2_new) * X_h2 * I_12_d

                p_gas_h2_d = S_gas_h2 * R * T_ad / 16
                Rho_T_8_d  = k_L_a * (S_h2_new - 16 * K_H_h2 * p_gas_h2_d)

                S_h2delta = (q_ad / V_liq * (si_S_h2 - S_h2_new)
                             + (1 - Y_su) * f_h2_su * Rho_5_d
                             + (1 - Y_aa) * f_h2_aa * Rho_6_d
                             + (1 - Y_fa) * 0.3 * Rho_7_d
                             + (1 - Y_c4) * 0.15 * Rho_8_d
                             + (1 - Y_c4) * 0.2  * Rho_9_d
                             + (1 - Y_pro) * 0.43 * Rho_10_d
                             - Rho_12_d - Rho_T_8_d)

                S_h2gradeq = (- 1.0 / V_liq * q_ad
                              - 3.0 / 10.0 * (1 - Y_fa) * k_m_fa * S_fa / (K_S_fa + S_fa) * X_fa * I_pH_aa_d / (1 + K_S_IN / S_IN) / ((1 + S_h2_new / K_I_h2_fa) ** 2) / K_I_h2_fa
                              - 3.0 / 20.0 * (1 - Y_c4) * k_m_c4 * S_va * S_va / (K_S_c4 + S_va) * X_c4 / (S_bu + S_va + eps) * I_pH_aa_d / (1 + K_S_IN / S_IN) / ((1 + S_h2_new / K_I_h2_c4) ** 2) / K_I_h2_c4
                              - 1.0 / 5.0  * (1 - Y_c4) * k_m_c4 * S_bu * S_bu / (K_S_c4 + S_bu) * X_c4 / (S_bu + S_va + eps) * I_pH_aa_d / (1 + K_S_IN / S_IN) / ((1 + S_h2_new / K_I_h2_c4) ** 2) / K_I_h2_c4
                              - 43.0 / 100.0 * (1 - Y_pro) * k_m_pro * S_pro / (K_S_pro + S_pro) * X_pro * I_pH_aa_d / (1 + K_S_IN / S_IN) / ((1 + S_h2_new / K_I_h2_pro) ** 2) / K_I_h2_pro
                              - k_m_h2 / (K_S_h2 + S_h2_new) * X_h2 * I_pH_h2_d / (1 + K_S_IN / S_IN)
                              + k_m_h2 * S_h2_new / ((K_S_h2 + S_h2_new) ** 2) * X_h2 * I_pH_h2_d / (1 + K_S_IN / S_IN)
                              - k_L_a)

                S_h2_new = S_h2_new - S_h2delta / S_h2gradeq
                if S_h2_new <= 0:
                    S_h2_new = tol
                j += 1

            return (S_H_ion, pH_new, S_h2_new,
                    S_va_ion_f, S_bu_ion_f, S_pro_ion_f, S_ac_ion_f, S_hco3_ion_f, S_nh3_f)

        # ------------------------------------------------------------------ #
        # Initial state vector and output dataframe setup                     #
        # ------------------------------------------------------------------ #
        state_zero = [
            S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac, S_h2, S_ch4,
            S_IC, S_IN, S_I,
            X_xc, X_ch, X_pr, X_li, X_su, X_aa, X_fa, X_c4, X_pro, X_ac, X_h2, X_I,
            S_cation, S_anion,
            S_H_ion,           # stored under column 'pH'; converted at end
            S_va_ion, S_bu_ion, S_pro_ion, S_ac_ion, S_hco3_ion,
            S_co2, S_nh3, S_nh4_ion,
            S_gas_h2, S_gas_ch4, S_gas_co2,
        ]

        columns = [
            "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac",
            "S_h2", "S_ch4", "S_IC", "S_IN", "S_I",
            "X_xc", "X_ch", "X_pr", "X_li",
            "X_su", "X_aa", "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
            "S_cation", "S_anion",
            "pH",          # holds S_H_ion during simulation; converted to pH at end
            "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion",
            "S_hco3_ion", "S_co2", "S_nh3", "S_nh4_ion",
            "S_gas_h2", "S_gas_ch4", "S_gas_co2",
        ]

        simulate_results = pd.DataFrame([state_zero], columns=columns)

        solvermethod = 'DOP853'
        t_arr = influent_state['time']
        t0 = 0
        n  = 0

        # ------------------------------------------------------------------ #
        # Dynamic simulation loop                                             #
        # ------------------------------------------------------------------ #
        for u in t_arr[1:]:
            n += 1
            state_input_ref[0] = get_influent(n)

            tstep = [t0, u]

            r = scipy.integrate.solve_ivp(ADM1_ODE, tstep, state_zero, method=solvermethod)
            sim = r.y  # shape (38, n_points)

            # Extract final state from ODE integration
            (S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac,
             S_h2, S_ch4, S_IC, S_IN, S_I,
             X_xc, X_ch, X_pr, X_li,
             X_su, X_aa, X_fa, X_c4, X_pro, X_ac, X_h2, X_I,
             S_cation, S_anion,
             S_H_ion,
             S_va_ion, S_bu_ion, S_pro_ion, S_ac_ion, S_hco3_ion,
             S_co2, S_nh3, S_nh4_ion,
             S_gas_h2, S_gas_ch4, S_gas_co2) = [sim[k, -1] for k in range(38)]

            # DAE solve: update S_H_ion, S_h2, ion species
            (S_H_ion, _pH, S_h2,
             S_va_ion, S_bu_ion, S_pro_ion, S_ac_ion, S_hco3_ion, S_nh3) = DAESolve(
                S_va, S_bu, S_pro, S_ac, S_IC, S_IN, S_cation, S_anion,
                S_h2, S_gas_h2, S_su, S_aa, S_fa,
                X_su, X_aa, X_fa, X_c4, X_pro, X_h2,
                S_H_ion,
            )

            # Algebraic updates
            p_gas_h2_  = S_gas_h2  * R * T_op / 16
            p_gas_ch4_ = S_gas_ch4 * R * T_op / 64
            p_gas_co2_ = S_gas_co2 * R * T_op
            p_gas_     = p_gas_h2_ + p_gas_ch4_ + p_gas_co2_ + p_gas_h2o
            q_gas_     = k_p * (p_gas_ - p_atm)
            if q_gas_ < 0:
                q_gas_ = 0.0

            S_nh4_ion = S_IN  - S_nh3
            S_co2     = S_IC  - S_hco3_ion

            # Rebuild state vector with updated values
            state_zero = [
                S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac, S_h2, S_ch4,
                S_IC, S_IN, S_I,
                X_xc, X_ch, X_pr, X_li, X_su, X_aa, X_fa, X_c4, X_pro, X_ac, X_h2, X_I,
                S_cation, S_anion,
                S_H_ion,   # stored as 'pH'; converted at end
                S_va_ion, S_bu_ion, S_pro_ion, S_ac_ion, S_hco3_ion,
                S_co2, S_nh3, S_nh4_ion,
                S_gas_h2, S_gas_ch4, S_gas_co2,
            ]

            df_row = pd.DataFrame([state_zero], columns=columns)
            simulate_results = pd.concat([simulate_results, df_row], ignore_index=True)
            t0 = u

        # Convert S_H_ion stored in 'pH' column to actual pH values
        simulate_results['pH'] = -np.log10(simulate_results['pH'])

        faasr_log(f"pyadm1: simulation complete — {len(simulate_results)} rows, {len(simulate_results.columns)} columns")

        simulate_results.to_csv(output_path, index=False)
        faasr_put_file(local_file=output_path, remote_folder=folder, remote_file=output1)

    faasr_log("pyadm1: done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---