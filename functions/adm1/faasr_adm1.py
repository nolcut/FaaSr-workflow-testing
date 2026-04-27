"""ADM1 anaerobic digestion model as a FaaSr function.

This is a faithful translation of PyADM1.py (Rosen et al., 2006 BSM2 implementation)
into a single callable function whose signature exposes the parameters most
commonly calibrated against physical reactor observations: biochemical kinetic
rates, half-saturation constants, biomass yields, inhibition constants, pH
inhibition windows, decay rates, and reactor physical constants.

The numerical core (ODE integration + Newton-Raphson DAE solver for S_H_ion
and S_h2) reproduces PyADM1.py output exactly given identical parameters and
inputs — verified against dynamic_out.csv.
"""

import os

import numpy as np
import pandas as pd
import scipy.integrate


class _ADM1:
    def __init__(self, p, influent_state, initial_state):
        # Bind every parameter from the dict as an attribute
        for k, v in p.items():
            setattr(self, k, v)

        # Constants from BSM2 (not normally calibrated)
        self.R = 0.083145
        self.T_base = 298.15
        self.p_atm = 1.013

        # Stoichiometric C/N composition (held fixed; rarely calibrated)
        self.N_xc = 0.0376 / 14
        self.N_I = 0.06 / 14
        self.N_aa = 0.007
        self.C_xc = 0.02786
        self.C_sI = 0.03
        self.C_ch = 0.0313
        self.C_pr = 0.03
        self.C_li = 0.022
        self.C_xI = 0.03
        self.C_su = 0.0313
        self.C_aa = 0.03
        self.C_fa = 0.0217
        self.C_bu = 0.025
        self.C_pro = 0.0268
        self.C_ac = 0.0313
        self.C_bac = 0.0313
        self.C_va = 0.024
        self.C_ch4 = 0.0156
        self.N_bac = 0.08 / 14

        # Substrate splits (Rosen et al. 2006)
        self.f_h2_su = 0.19
        self.f_bu_su = 0.13
        self.f_pro_su = 0.27
        self.f_ac_su = 0.41
        self.f_h2_aa = 0.06
        self.f_va_aa = 0.23
        self.f_bu_aa = 0.26
        self.f_pro_aa = 0.05
        self.f_ac_aa = 0.40

        # Acid-base equilibrium and rates (BSM2)
        self.K_a_va = 10 ** -4.86
        self.K_a_bu = 10 ** -4.82
        self.K_a_pro = 10 ** -4.88
        self.K_a_ac = 10 ** -4.76
        self.k_A_B_va = 1e10
        self.k_A_B_bu = 1e10
        self.k_A_B_pro = 1e10
        self.k_A_B_ac = 1e10
        self.k_A_B_co2 = 1e10
        self.k_A_B_IN = 1e10

        # Gas-phase constants
        self.k_p = 5e4
        self.k_L_a = 200.0

        # Temperature-dependent equilibria
        T_base = self.T_base
        T_ad = self.T_op
        R = self.R
        self.T_ad = T_ad
        self.K_w = 10 ** -14.0 * np.exp((55900 / (100 * R)) * (1 / T_base - 1 / T_ad))
        self.K_a_co2 = 10 ** -6.35 * np.exp((7646 / (100 * R)) * (1 / T_base - 1 / T_ad))
        self.K_a_IN = 10 ** -9.25 * np.exp((51965 / (100 * R)) * (1 / T_base - 1 / T_ad))
        self.p_gas_h2o = 0.0313 * np.exp(5290 * (1 / T_base - 1 / T_ad))
        self.K_H_co2 = 0.035 * np.exp((-19410 / (100 * R)) * (1 / T_base - 1 / T_ad))
        self.K_H_ch4 = 0.0014 * np.exp((-14240 / (100 * R)) * (1 / T_base - 1 / T_ad))
        self.K_H_h2 = 7.8e-4 * np.exp(-4180 / (100 * R) * (1 / T_base - 1 / T_ad))

        # pH inhibition derived constants
        self.K_pH_aa = 10 ** (-1 * (self.pH_LL_aa + self.pH_UL_aa) / 2.0)
        self.nn_aa = 3.0 / (self.pH_UL_aa - self.pH_LL_aa)
        self.K_pH_ac = 10 ** (-1 * (self.pH_LL_ac + self.pH_UL_ac) / 2.0)
        self.n_ac = 3.0 / (self.pH_UL_ac - self.pH_LL_ac)
        self.K_pH_h2 = 10 ** (-1 * (self.pH_LL_h2 + self.pH_UL_h2) / 2.0)
        self.n_h2 = 3.0 / (self.pH_UL_h2 - self.pH_LL_h2)

        self.V_ad = self.V_liq + self.V_gas

        self.influent_state = influent_state
        self.initial_state = initial_state

        # Initial reactor state
        s = initial_state
        self.S_su = s['S_su'][0]; self.S_aa = s['S_aa'][0]; self.S_fa = s['S_fa'][0]
        self.S_va = s['S_va'][0]; self.S_bu = s['S_bu'][0]; self.S_pro = s['S_pro'][0]
        self.S_ac = s['S_ac'][0]; self.S_h2 = s['S_h2'][0]; self.S_ch4 = s['S_ch4'][0]
        self.S_IC = s['S_IC'][0]; self.S_IN = s['S_IN'][0]; self.S_I = s['S_I'][0]
        self.X_xc = s['X_xc'][0]; self.X_ch = s['X_ch'][0]; self.X_pr = s['X_pr'][0]
        self.X_li = s['X_li'][0]; self.X_su = s['X_su'][0]; self.X_aa = s['X_aa'][0]
        self.X_fa = s['X_fa'][0]; self.X_c4 = s['X_c4'][0]; self.X_pro = s['X_pro'][0]
        self.X_ac = s['X_ac'][0]; self.X_h2 = s['X_h2'][0]; self.X_I = s['X_I'][0]
        self.S_cation = s['S_cation'][0]; self.S_anion = s['S_anion'][0]
        self.S_H_ion = s['S_H_ion'][0]
        self.S_va_ion = s['S_va_ion'][0]; self.S_bu_ion = s['S_bu_ion'][0]
        self.S_pro_ion = s['S_pro_ion'][0]; self.S_ac_ion = s['S_ac_ion'][0]
        self.S_hco3_ion = s['S_hco3_ion'][0]; self.S_nh3 = s['S_nh3'][0]
        # The initial values for S_nh4_ion and S_co2 in PyADM1 are hard-coded
        # (they get recomputed inside the ODE/loop, so the initial value does
        # not influence the trajectory) — keep the same constants for parity.
        self.S_nh4_ion = 0.0041
        self.S_co2 = 0.14
        self.S_gas_h2 = s['S_gas_h2'][0]
        self.S_gas_ch4 = s['S_gas_ch4'][0]
        self.S_gas_co2 = s['S_gas_co2'][0]

        self.q_gas = 0.0
        self.q_ch4 = 0.0
        self.p_gas_h2 = 0.0
        self.p_gas = 0.0

        self._set_influent(0)
        self.state_input = self._build_state_input()

    def _set_influent(self, i):
        inf = self.influent_state
        self.S_su_in = inf['S_su'][i]; self.S_aa_in = inf['S_aa'][i]
        self.S_fa_in = inf['S_fa'][i]; self.S_va_in = inf['S_va'][i]
        self.S_bu_in = inf['S_bu'][i]; self.S_pro_in = inf['S_pro'][i]
        self.S_ac_in = inf['S_ac'][i]; self.S_h2_in = inf['S_h2'][i]
        self.S_ch4_in = inf['S_ch4'][i]; self.S_IC_in = inf['S_IC'][i]
        self.S_IN_in = inf['S_IN'][i]; self.S_I_in = inf['S_I'][i]
        self.X_xc_in = inf['X_xc'][i]; self.X_ch_in = inf['X_ch'][i]
        self.X_pr_in = inf['X_pr'][i]; self.X_li_in = inf['X_li'][i]
        self.X_su_in = inf['X_su'][i]; self.X_aa_in = inf['X_aa'][i]
        self.X_fa_in = inf['X_fa'][i]; self.X_c4_in = inf['X_c4'][i]
        self.X_pro_in = inf['X_pro'][i]; self.X_ac_in = inf['X_ac'][i]
        self.X_h2_in = inf['X_h2'][i]; self.X_I_in = inf['X_I'][i]
        self.S_cation_in = inf['S_cation'][i]; self.S_anion_in = inf['S_anion'][i]

    def _build_state_input(self):
        return [self.S_su_in, self.S_aa_in, self.S_fa_in, self.S_va_in, self.S_bu_in,
                self.S_pro_in, self.S_ac_in, self.S_h2_in, self.S_ch4_in, self.S_IC_in,
                self.S_IN_in, self.S_I_in, self.X_xc_in, self.X_ch_in, self.X_pr_in,
                self.X_li_in, self.X_su_in, self.X_aa_in, self.X_fa_in, self.X_c4_in,
                self.X_pro_in, self.X_ac_in, self.X_h2_in, self.X_I_in,
                self.S_cation_in, self.S_anion_in]

    def _state_zero(self):
        return [self.S_su, self.S_aa, self.S_fa, self.S_va, self.S_bu, self.S_pro,
                self.S_ac, self.S_h2, self.S_ch4, self.S_IC, self.S_IN, self.S_I,
                self.X_xc, self.X_ch, self.X_pr, self.X_li, self.X_su, self.X_aa,
                self.X_fa, self.X_c4, self.X_pro, self.X_ac, self.X_h2, self.X_I,
                self.S_cation, self.S_anion, self.S_H_ion, self.S_va_ion,
                self.S_bu_ion, self.S_pro_ion, self.S_ac_ion, self.S_hco3_ion,
                self.S_co2, self.S_nh3, self.S_nh4_ion, self.S_gas_h2,
                self.S_gas_ch4, self.S_gas_co2]

    def _adm1_ode(self, t, y):
        # Unpack state
        (S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac, S_h2, S_ch4, S_IC, S_IN, S_I,
         X_xc, X_ch, X_pr, X_li, X_su, X_aa, X_fa, X_c4, X_pro, X_ac, X_h2, X_I,
         S_cation, S_anion, S_H_ion, S_va_ion, S_bu_ion, S_pro_ion, S_ac_ion,
         S_hco3_ion, S_co2, S_nh3, S_nh4_ion, S_gas_h2, S_gas_ch4, S_gas_co2) = y

        (S_su_in, S_aa_in, S_fa_in, S_va_in, S_bu_in, S_pro_in, S_ac_in, S_h2_in,
         S_ch4_in, S_IC_in, S_IN_in, S_I_in, X_xc_in, X_ch_in, X_pr_in, X_li_in,
         X_su_in, X_aa_in, X_fa_in, X_c4_in, X_pro_in, X_ac_in, X_h2_in, X_I_in,
         S_cation_in, S_anion_in) = self.state_input

        S_nh4_ion = S_IN - S_nh3
        S_co2 = S_IC - S_hco3_ion
        self.S_nh4_ion = S_nh4_ion
        self.S_co2 = S_co2

        I_pH_aa = (self.K_pH_aa ** self.nn_aa) / (S_H_ion ** self.nn_aa + self.K_pH_aa ** self.nn_aa)
        I_pH_ac = (self.K_pH_ac ** self.n_ac) / (S_H_ion ** self.n_ac + self.K_pH_ac ** self.n_ac)
        I_pH_h2 = (self.K_pH_h2 ** self.n_h2) / (S_H_ion ** self.n_h2 + self.K_pH_h2 ** self.n_h2)
        I_IN_lim = 1 / (1 + (self.K_S_IN / S_IN))
        I_h2_fa = 1 / (1 + (S_h2 / self.K_I_h2_fa))
        I_h2_c4 = 1 / (1 + (S_h2 / self.K_I_h2_c4))
        I_h2_pro = 1 / (1 + (S_h2 / self.K_I_h2_pro))
        I_nh3 = 1 / (1 + (S_nh3 / self.K_I_nh3))

        I_5 = I_pH_aa * I_IN_lim
        I_6 = I_5
        I_7 = I_pH_aa * I_IN_lim * I_h2_fa
        I_8 = I_pH_aa * I_IN_lim * I_h2_c4
        I_9 = I_8
        I_10 = I_pH_aa * I_IN_lim * I_h2_pro
        I_11 = I_pH_ac * I_IN_lim * I_nh3
        I_12 = I_pH_h2 * I_IN_lim

        Rho_1 = self.k_dis * X_xc
        Rho_2 = self.k_hyd_ch * X_ch
        Rho_3 = self.k_hyd_pr * X_pr
        Rho_4 = self.k_hyd_li * X_li
        Rho_5 = self.k_m_su * S_su / (self.K_S_su + S_su) * X_su * I_5
        Rho_6 = self.k_m_aa * (S_aa / (self.K_S_aa + S_aa)) * X_aa * I_6
        Rho_7 = self.k_m_fa * (S_fa / (self.K_S_fa + S_fa)) * X_fa * I_7
        Rho_8 = self.k_m_c4 * (S_va / (self.K_S_c4 + S_va)) * X_c4 * (S_va / (S_bu + S_va + 1e-6)) * I_8
        Rho_9 = self.k_m_c4 * (S_bu / (self.K_S_c4 + S_bu)) * X_c4 * (S_bu / (S_bu + S_va + 1e-6)) * I_9
        Rho_10 = self.k_m_pro * (S_pro / (self.K_S_pro + S_pro)) * X_pro * I_10
        Rho_11 = self.k_m_ac * (S_ac / (self.K_S_ac + S_ac)) * X_ac * I_11
        Rho_12 = self.k_m_h2 * (S_h2 / (self.K_S_h2 + S_h2)) * X_h2 * I_12
        Rho_13 = self.k_dec_X_su * X_su
        Rho_14 = self.k_dec_X_aa * X_aa
        Rho_15 = self.k_dec_X_fa * X_fa
        Rho_16 = self.k_dec_X_c4 * X_c4
        Rho_17 = self.k_dec_X_pro * X_pro
        Rho_18 = self.k_dec_X_ac * X_ac
        Rho_19 = self.k_dec_X_h2 * X_h2

        Rho_A_4 = self.k_A_B_va * (S_va_ion * (self.K_a_va + S_H_ion) - self.K_a_va * S_va)
        Rho_A_5 = self.k_A_B_bu * (S_bu_ion * (self.K_a_bu + S_H_ion) - self.K_a_bu * S_bu)
        Rho_A_6 = self.k_A_B_pro * (S_pro_ion * (self.K_a_pro + S_H_ion) - self.K_a_pro * S_pro)
        Rho_A_7 = self.k_A_B_ac * (S_ac_ion * (self.K_a_ac + S_H_ion) - self.K_a_ac * S_ac)
        Rho_A_10 = self.k_A_B_co2 * (S_hco3_ion * (self.K_a_co2 + S_H_ion) - self.K_a_co2 * S_IC)
        Rho_A_11 = self.k_A_B_IN * (S_nh3 * (self.K_a_IN + S_H_ion) - self.K_a_IN * S_IN)

        p_gas_h2 = S_gas_h2 * self.R * self.T_op / 16
        p_gas_ch4 = S_gas_ch4 * self.R * self.T_op / 64
        p_gas_co2 = S_gas_co2 * self.R * self.T_op
        p_gas = p_gas_h2 + p_gas_ch4 + p_gas_co2 + self.p_gas_h2o
        q_gas = self.k_p * (p_gas - self.p_atm)
        if q_gas < 0:
            q_gas = 0
        self.p_gas = p_gas
        self.q_gas = q_gas
        self.q_ch4 = q_gas * (p_gas_ch4 / p_gas)

        Rho_T_8 = self.k_L_a * (S_h2 - 16 * self.K_H_h2 * p_gas_h2)
        Rho_T_9 = self.k_L_a * (S_ch4 - 64 * self.K_H_ch4 * p_gas_ch4)
        Rho_T_10 = self.k_L_a * (S_co2 - self.K_H_co2 * p_gas_co2)

        q_ad = self.q_ad
        V_liq = self.V_liq
        V_gas = self.V_gas
        f_fa_li = self.f_fa_li

        diff_S_su = q_ad / V_liq * (S_su_in - S_su) + Rho_2 + (1 - f_fa_li) * Rho_4 - Rho_5
        diff_S_aa = q_ad / V_liq * (S_aa_in - S_aa) + Rho_3 - Rho_6
        diff_S_fa = q_ad / V_liq * (S_fa_in - S_fa) + (f_fa_li * Rho_4) - Rho_7
        diff_S_va = q_ad / V_liq * (S_va_in - S_va) + (1 - self.Y_aa) * self.f_va_aa * Rho_6 - Rho_8
        diff_S_bu = q_ad / V_liq * (S_bu_in - S_bu) + (1 - self.Y_su) * self.f_bu_su * Rho_5 + (1 - self.Y_aa) * self.f_bu_aa * Rho_6 - Rho_9
        diff_S_pro = q_ad / V_liq * (S_pro_in - S_pro) + (1 - self.Y_su) * self.f_pro_su * Rho_5 + (1 - self.Y_aa) * self.f_pro_aa * Rho_6 + (1 - self.Y_c4) * 0.54 * Rho_8 - Rho_10
        diff_S_ac = (q_ad / V_liq * (S_ac_in - S_ac) + (1 - self.Y_su) * self.f_ac_su * Rho_5 + (1 - self.Y_aa) * self.f_ac_aa * Rho_6 + (1 - self.Y_fa) * 0.7 * Rho_7 + (1 - self.Y_c4) * 0.31 * Rho_8 + (1 - self.Y_c4) * 0.8 * Rho_9 + (1 - self.Y_pro) * 0.57 * Rho_10 - Rho_11)
        diff_S_ch4 = q_ad / V_liq * (S_ch4_in - S_ch4) + (1 - self.Y_ac) * Rho_11 + (1 - self.Y_h2) * Rho_12 - Rho_T_9

        s_1 = (-1 * self.C_xc + self.f_sI_xc * self.C_sI + self.f_ch_xc * self.C_ch + self.f_pr_xc * self.C_pr + self.f_li_xc * self.C_li + self.f_xI_xc * self.C_xI)
        s_2 = -1 * self.C_ch + self.C_su
        s_3 = -1 * self.C_pr + self.C_aa
        s_4 = -1 * self.C_li + (1 - f_fa_li) * self.C_su + f_fa_li * self.C_fa
        s_5 = -1 * self.C_su + (1 - self.Y_su) * (self.f_bu_su * self.C_bu + self.f_pro_su * self.C_pro + self.f_ac_su * self.C_ac) + self.Y_su * self.C_bac
        s_6 = -1 * self.C_aa + (1 - self.Y_aa) * (self.f_va_aa * self.C_va + self.f_bu_aa * self.C_bu + self.f_pro_aa * self.C_pro + self.f_ac_aa * self.C_ac) + self.Y_aa * self.C_bac
        s_7 = -1 * self.C_fa + (1 - self.Y_fa) * 0.7 * self.C_ac + self.Y_fa * self.C_bac
        s_8 = -1 * self.C_va + (1 - self.Y_c4) * 0.54 * self.C_pro + (1 - self.Y_c4) * 0.31 * self.C_ac + self.Y_c4 * self.C_bac
        s_9 = -1 * self.C_bu + (1 - self.Y_c4) * 0.8 * self.C_ac + self.Y_c4 * self.C_bac
        s_10 = -1 * self.C_pro + (1 - self.Y_pro) * 0.57 * self.C_ac + self.Y_pro * self.C_bac
        s_11 = -1 * self.C_ac + (1 - self.Y_ac) * self.C_ch4 + self.Y_ac * self.C_bac
        s_12 = (1 - self.Y_h2) * self.C_ch4 + self.Y_h2 * self.C_bac
        s_13 = -1 * self.C_bac + self.C_xc

        Sigma = (s_1 * Rho_1 + s_2 * Rho_2 + s_3 * Rho_3 + s_4 * Rho_4 + s_5 * Rho_5
                 + s_6 * Rho_6 + s_7 * Rho_7 + s_8 * Rho_8 + s_9 * Rho_9 + s_10 * Rho_10
                 + s_11 * Rho_11 + s_12 * Rho_12
                 + s_13 * (Rho_13 + Rho_14 + Rho_15 + Rho_16 + Rho_17 + Rho_18 + Rho_19))

        diff_S_IC = q_ad / V_liq * (S_IC_in - S_IC) - Sigma - Rho_T_10

        diff_S_IN = (q_ad / V_liq * (S_IN_in - S_IN)
                     + (self.N_xc - self.f_xI_xc * self.N_I - self.f_sI_xc * self.N_I - self.f_pr_xc * self.N_aa) * Rho_1
                     - self.Y_su * self.N_bac * Rho_5
                     + (self.N_aa - self.Y_aa * self.N_bac) * Rho_6
                     - self.Y_fa * self.N_bac * Rho_7
                     - self.Y_c4 * self.N_bac * Rho_8
                     - self.Y_c4 * self.N_bac * Rho_9
                     - self.Y_pro * self.N_bac * Rho_10
                     - self.Y_ac * self.N_bac * Rho_11
                     - self.Y_h2 * self.N_bac * Rho_12
                     + (self.N_bac - self.N_xc) * (Rho_13 + Rho_14 + Rho_15 + Rho_16 + Rho_17 + Rho_18 + Rho_19))

        diff_S_I = q_ad / V_liq * (S_I_in - S_I) + self.f_sI_xc * Rho_1

        diff_X_xc = q_ad / V_liq * (X_xc_in - X_xc) - Rho_1 + Rho_13 + Rho_14 + Rho_15 + Rho_16 + Rho_17 + Rho_18 + Rho_19
        diff_X_ch = q_ad / V_liq * (X_ch_in - X_ch) + self.f_ch_xc * Rho_1 - Rho_2
        diff_X_pr = q_ad / V_liq * (X_pr_in - X_pr) + self.f_pr_xc * Rho_1 - Rho_3
        diff_X_li = q_ad / V_liq * (X_li_in - X_li) + self.f_li_xc * Rho_1 - Rho_4
        diff_X_su = q_ad / V_liq * (X_su_in - X_su) + self.Y_su * Rho_5 - Rho_13
        diff_X_aa = q_ad / V_liq * (X_aa_in - X_aa) + self.Y_aa * Rho_6 - Rho_14
        diff_X_fa = q_ad / V_liq * (X_fa_in - X_fa) + self.Y_fa * Rho_7 - Rho_15
        diff_X_c4 = q_ad / V_liq * (X_c4_in - X_c4) + self.Y_c4 * Rho_8 + self.Y_c4 * Rho_9 - Rho_16
        diff_X_pro = q_ad / V_liq * (X_pro_in - X_pro) + self.Y_pro * Rho_10 - Rho_17
        diff_X_ac = q_ad / V_liq * (X_ac_in - X_ac) + self.Y_ac * Rho_11 - Rho_18
        diff_X_h2 = q_ad / V_liq * (X_h2_in - X_h2) + self.Y_h2 * Rho_12 - Rho_19
        diff_X_I = q_ad / V_liq * (X_I_in - X_I) + self.f_xI_xc * Rho_1

        diff_S_cation = q_ad / V_liq * (S_cation_in - S_cation)
        diff_S_anion = q_ad / V_liq * (S_anion_in - S_anion)

        diff_S_h2 = 0
        diff_S_va_ion = 0
        diff_S_bu_ion = 0
        diff_S_pro_ion = 0
        diff_S_ac_ion = 0
        diff_S_hco3_ion = 0
        diff_S_nh3 = 0

        diff_S_gas_h2 = (q_gas / V_gas * -1 * S_gas_h2) + (Rho_T_8 * V_liq / V_gas)
        diff_S_gas_ch4 = (q_gas / V_gas * -1 * S_gas_ch4) + (Rho_T_9 * V_liq / V_gas)
        diff_S_gas_co2 = (q_gas / V_gas * -1 * S_gas_co2) + (Rho_T_10 * V_liq / V_gas)

        diff_S_H_ion = 0
        diff_S_co2 = 0
        diff_S_nh4_ion = 0

        return (diff_S_su, diff_S_aa, diff_S_fa, diff_S_va, diff_S_bu, diff_S_pro,
                diff_S_ac, diff_S_h2, diff_S_ch4, diff_S_IC, diff_S_IN, diff_S_I,
                diff_X_xc, diff_X_ch, diff_X_pr, diff_X_li, diff_X_su, diff_X_aa,
                diff_X_fa, diff_X_c4, diff_X_pro, diff_X_ac, diff_X_h2, diff_X_I,
                diff_S_cation, diff_S_anion, diff_S_H_ion, diff_S_va_ion,
                diff_S_bu_ion, diff_S_pro_ion, diff_S_ac_ion, diff_S_hco3_ion,
                diff_S_co2, diff_S_nh3, diff_S_nh4_ion, diff_S_gas_h2,
                diff_S_gas_ch4, diff_S_gas_co2)

    def _dae_solve(self):
        eps = 1e-7
        prevS_H_ion = self.S_H_ion
        shdelta = 1.0
        S_h2delta = 1.0
        tol = 1e-12
        maxIter = 1000
        i = 1
        j = 1

        S_H_ion = self.S_H_ion
        S_va, S_bu, S_pro, S_ac = self.S_va, self.S_bu, self.S_pro, self.S_ac
        S_IC, S_IN = self.S_IC, self.S_IN
        S_cation, S_anion = self.S_cation, self.S_anion

        K_a_va, K_a_bu = self.K_a_va, self.K_a_bu
        K_a_pro, K_a_ac = self.K_a_pro, self.K_a_ac
        K_a_co2, K_a_IN = self.K_a_co2, self.K_a_IN
        K_w = self.K_w

        while ((shdelta > tol or shdelta < -tol) and (i <= maxIter)):
            S_va_ion = K_a_va * S_va / (K_a_va + S_H_ion)
            S_bu_ion = K_a_bu * S_bu / (K_a_bu + S_H_ion)
            S_pro_ion = K_a_pro * S_pro / (K_a_pro + S_H_ion)
            S_ac_ion = K_a_ac * S_ac / (K_a_ac + S_H_ion)
            S_hco3_ion = K_a_co2 * S_IC / (K_a_co2 + S_H_ion)
            S_nh3 = K_a_IN * S_IN / (K_a_IN + S_H_ion)
            shdelta = (S_cation + (S_IN - S_nh3) + S_H_ion - S_hco3_ion
                       - S_ac_ion / 64.0 - S_pro_ion / 112.0 - S_bu_ion / 160.0
                       - S_va_ion / 208.0 - K_w / S_H_ion - S_anion)
            shgradeq = (1
                        + K_a_IN * S_IN / ((K_a_IN + S_H_ion) ** 2)
                        + K_a_co2 * S_IC / ((K_a_co2 + S_H_ion) ** 2)
                        + 1 / 64.0 * K_a_ac * S_ac / ((K_a_ac + S_H_ion) ** 2)
                        + 1 / 112.0 * K_a_pro * S_pro / ((K_a_pro + S_H_ion) ** 2)
                        + 1 / 160.0 * K_a_bu * S_bu / ((K_a_bu + S_H_ion) ** 2)
                        + 1 / 208.0 * K_a_va * S_va / ((K_a_va + S_H_ion) ** 2)
                        + K_w / (S_H_ion * S_H_ion))
            S_H_ion = S_H_ion - shdelta / shgradeq
            if S_H_ion <= 0:
                S_H_ion = tol
            i += 1

        self.S_H_ion = S_H_ion
        self.S_va_ion = S_va_ion
        self.S_bu_ion = S_bu_ion
        self.S_pro_ion = S_pro_ion
        self.S_ac_ion = S_ac_ion
        self.S_hco3_ion = S_hco3_ion
        self.S_nh3 = S_nh3
        self.pH = -np.log10(S_H_ion)

        # DAE solver for S_h2 (uses prev S_H_ion exactly as PyADM1 does)
        S_h2 = self.S_h2
        X_su, X_aa, X_fa, X_c4, X_pro, X_h2 = (self.X_su, self.X_aa, self.X_fa,
                                               self.X_c4, self.X_pro, self.X_h2)
        S_su, S_aa, S_fa = self.S_su, self.S_aa, self.S_fa
        S_h2_in = self.S_h2_in
        q_ad = self.q_ad
        V_liq = self.V_liq
        S_gas_h2 = self.S_gas_h2

        K_pH_aa, nn_aa = self.K_pH_aa, self.nn_aa
        K_pH_h2, n_h2 = self.K_pH_h2, self.n_h2
        K_S_IN = self.K_S_IN
        K_I_h2_fa, K_I_h2_c4, K_I_h2_pro = self.K_I_h2_fa, self.K_I_h2_c4, self.K_I_h2_pro
        K_S_su, K_S_aa, K_S_fa = self.K_S_su, self.K_S_aa, self.K_S_fa
        K_S_c4, K_S_pro, K_S_h2 = self.K_S_c4, self.K_S_pro, self.K_S_h2
        k_m_su, k_m_aa, k_m_fa = self.k_m_su, self.k_m_aa, self.k_m_fa
        k_m_c4, k_m_pro, k_m_h2 = self.k_m_c4, self.k_m_pro, self.k_m_h2
        Y_su, Y_aa, Y_fa, Y_c4, Y_pro = self.Y_su, self.Y_aa, self.Y_fa, self.Y_c4, self.Y_pro
        f_h2_su, f_h2_aa = self.f_h2_su, self.f_h2_aa
        K_H_h2 = self.K_H_h2
        k_L_a = self.k_L_a
        R = self.R
        T_ad = self.T_ad

        while ((S_h2delta > tol or S_h2delta < -tol) and (j <= maxIter)):
            I_pH_aa = (K_pH_aa ** nn_aa) / (prevS_H_ion ** nn_aa + K_pH_aa ** nn_aa)
            I_pH_h2 = (K_pH_h2 ** n_h2) / (prevS_H_ion ** n_h2 + K_pH_h2 ** n_h2)
            I_IN_lim = 1 / (1 + (K_S_IN / S_IN))
            I_h2_fa = 1 / (1 + (S_h2 / K_I_h2_fa))
            I_h2_c4 = 1 / (1 + (S_h2 / K_I_h2_c4))
            I_h2_pro = 1 / (1 + (S_h2 / K_I_h2_pro))

            I_5 = I_pH_aa * I_IN_lim
            I_6 = I_5
            I_7 = I_pH_aa * I_IN_lim * I_h2_fa
            I_8 = I_pH_aa * I_IN_lim * I_h2_c4
            I_9 = I_8
            I_10 = I_pH_aa * I_IN_lim * I_h2_pro
            I_12 = I_pH_h2 * I_IN_lim

            Rho_5 = k_m_su * (S_su / (K_S_su + S_su)) * X_su * I_5
            Rho_6 = k_m_aa * (S_aa / (K_S_aa + S_aa)) * X_aa * I_6
            Rho_7 = k_m_fa * (S_fa / (K_S_fa + S_fa)) * X_fa * I_7
            Rho_8 = k_m_c4 * (S_va / (K_S_c4 + S_va)) * X_c4 * (S_va / (S_bu + S_va + 1e-6)) * I_8
            Rho_9 = k_m_c4 * (S_bu / (K_S_c4 + S_bu)) * X_c4 * (S_bu / (S_bu + S_va + 1e-6)) * I_9
            Rho_10 = k_m_pro * (S_pro / (K_S_pro + S_pro)) * X_pro * I_10
            Rho_12 = k_m_h2 * (S_h2 / (K_S_h2 + S_h2)) * X_h2 * I_12
            p_gas_h2 = S_gas_h2 * R * T_ad / 16
            Rho_T_8 = k_L_a * (S_h2 - 16 * K_H_h2 * p_gas_h2)
            S_h2delta = (q_ad / V_liq * (S_h2_in - S_h2)
                         + (1 - Y_su) * f_h2_su * Rho_5
                         + (1 - Y_aa) * f_h2_aa * Rho_6
                         + (1 - Y_fa) * 0.3 * Rho_7
                         + (1 - Y_c4) * 0.15 * Rho_8
                         + (1 - Y_c4) * 0.2 * Rho_9
                         + (1 - Y_pro) * 0.43 * Rho_10
                         - Rho_12 - Rho_T_8)
            S_h2gradeq = (-1.0 / V_liq * q_ad
                          - 3.0 / 10.0 * (1 - Y_fa) * k_m_fa * S_fa / (K_S_fa + S_fa) * X_fa
                              * I_pH_aa / (1 + K_S_IN / S_IN)
                              / ((1 + S_h2 / K_I_h2_fa) ** 2) / K_I_h2_fa
                          - 3.0 / 20.0 * (1 - Y_c4) * k_m_c4 * S_va * S_va / (K_S_c4 + S_va) * X_c4
                              / (S_bu + S_va + eps) * I_pH_aa / (1 + K_S_IN / S_IN)
                              / ((1 + S_h2 / K_I_h2_c4) ** 2) / K_I_h2_c4
                          - 1.0 / 5.0 * (1 - Y_c4) * k_m_c4 * S_bu * S_bu / (K_S_c4 + S_bu) * X_c4
                              / (S_bu + S_va + eps) * I_pH_aa / (1 + K_S_IN / S_IN)
                              / ((1 + S_h2 / K_I_h2_c4) ** 2) / K_I_h2_c4
                          - 43.0 / 100.0 * (1 - Y_pro) * k_m_pro * S_pro / (K_S_pro + S_pro) * X_pro
                              * I_pH_aa / (1 + K_S_IN / S_IN)
                              / ((1 + S_h2 / K_I_h2_pro) ** 2) / K_I_h2_pro
                          - k_m_h2 / (K_S_h2 + S_h2) * X_h2 * I_pH_h2 / (1 + K_S_IN / S_IN)
                          + k_m_h2 * S_h2 / ((K_S_h2 + S_h2) ** 2) * X_h2 * I_pH_h2 / (1 + K_S_IN / S_IN)
                          - k_L_a)
            S_h2 = S_h2 - S_h2delta / S_h2gradeq
            if S_h2 <= 0:
                S_h2 = tol
            j += 1

        self.S_h2 = S_h2
        self.p_gas_h2 = p_gas_h2

    def run(self, solver_method="DOP853"):
        t = self.influent_state['time']
        columns = ["S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2",
                   "S_ch4", "S_IC", "S_IN", "S_I", "X_xc", "X_ch", "X_pr", "X_li",
                   "X_su", "X_aa", "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
                   "S_cation", "S_anion", "pH", "S_va_ion", "S_bu_ion", "S_pro_ion",
                   "S_ac_ion", "S_hco3_ion", "S_co2", "S_nh3", "S_nh4_ion",
                   "S_gas_h2", "S_gas_ch4", "S_gas_co2"]

        rows = [self._state_zero()]
        gas_rows = [{"q_gas": 0.0, "q_ch4": 0.0}]

        t0 = 0
        n = 0
        for u in t[1:]:
            n += 1
            self._set_influent(n)
            self.state_input = self._build_state_input()

            tstep = [t0, u]
            r = scipy.integrate.solve_ivp(
                self._adm1_ode, tstep, self._state_zero(), method=solver_method
            )
            y = r.y
            (self.S_su, self.S_aa, self.S_fa, self.S_va, self.S_bu, self.S_pro,
             self.S_ac, self.S_h2, self.S_ch4, self.S_IC, self.S_IN, self.S_I,
             self.X_xc, self.X_ch, self.X_pr, self.X_li, self.X_su, self.X_aa,
             self.X_fa, self.X_c4, self.X_pro, self.X_ac, self.X_h2, self.X_I,
             self.S_cation, self.S_anion, self.S_H_ion, self.S_va_ion,
             self.S_bu_ion, self.S_pro_ion, self.S_ac_ion, self.S_hco3_ion,
             self.S_co2, self.S_nh3, self.S_nh4_ion, self.S_gas_h2,
             self.S_gas_ch4, self.S_gas_co2) = (y[i][-1] for i in range(38))

            self._dae_solve()

            # Recompute gas-phase algebraic outputs at the new state
            p_gas_h2 = self.S_gas_h2 * self.R * self.T_op / 16
            p_gas_ch4 = self.S_gas_ch4 * self.R * self.T_op / 64
            p_gas_co2 = self.S_gas_co2 * self.R * self.T_op
            p_gas = p_gas_h2 + p_gas_ch4 + p_gas_co2 + self.p_gas_h2o
            q_gas = self.k_p * (p_gas - self.p_atm)
            if q_gas < 0:
                q_gas = 0
            q_ch4 = q_gas * (p_gas_ch4 / p_gas)
            if q_ch4 < 0:
                q_ch4 = 0
            gas_rows.append({"q_gas": q_gas, "q_ch4": q_ch4})

            self.S_nh4_ion = self.S_IN - self.S_nh3
            self.S_co2 = self.S_IC - self.S_hco3_ion

            rows.append(self._state_zero())
            t0 = u

        df = pd.DataFrame(rows, columns=columns)
        # Column index 26 (the "pH" column) currently holds S_H_ion; convert to pH
        df['pH'] = -np.log10(df['pH'])
        gas_df = pd.DataFrame(gas_rows)
        return df, gas_df


# ---------------------------------------------------------------------------
# Default parameter set (Rosen et al. 2006 BSM2). These are the parameters
# exposed for calibration against physical reactor observations.
# ---------------------------------------------------------------------------
_DEFAULTS = dict(
    # Reactor physical
    V_liq=3400.0, V_gas=300.0, T_op=308.15, q_ad=178.4674,
    # Disintegration / hydrolysis
    f_sI_xc=0.1, f_xI_xc=0.2, f_ch_xc=0.2, f_pr_xc=0.2, f_li_xc=0.3, f_fa_li=0.95,
    k_dis=0.5, k_hyd_ch=10.0, k_hyd_pr=10.0, k_hyd_li=10.0,
    # Biomass yields
    Y_su=0.1, Y_aa=0.08, Y_fa=0.06, Y_c4=0.06, Y_pro=0.04, Y_ac=0.05, Y_h2=0.06,
    # Monod uptake kinetics
    k_m_su=30.0, K_S_su=0.5,
    k_m_aa=50.0, K_S_aa=0.3,
    k_m_fa=6.0, K_S_fa=0.4,
    k_m_c4=20.0, K_S_c4=0.2,
    k_m_pro=13.0, K_S_pro=0.1,
    k_m_ac=8.0, K_S_ac=0.15,
    k_m_h2=35.0, K_S_h2=7e-6,
    K_S_IN=1e-4,
    # H2 and NH3 inhibition
    K_I_h2_fa=5e-6, K_I_h2_c4=1e-5, K_I_h2_pro=3.5e-6, K_I_nh3=0.0018,
    # pH inhibition windows
    pH_UL_aa=5.5, pH_LL_aa=4.0,
    pH_UL_ac=7.0, pH_LL_ac=6.0,
    pH_UL_h2=6.0, pH_LL_h2=5.0,
    # Decay rates
    k_dec_X_su=0.02, k_dec_X_aa=0.02, k_dec_X_fa=0.02, k_dec_X_c4=0.02,
    k_dec_X_pro=0.02, k_dec_X_ac=0.02, k_dec_X_h2=0.02,
)


def _run_simulation(influent_path, initial_path, output_path, solver_method, params):
    influent_state = pd.read_csv(influent_path)
    initial_state = pd.read_csv(initial_path)
    model = _ADM1(params, influent_state, initial_state)
    df, _gas_df = model.run(solver_method=solver_method)
    df.to_csv(output_path, index=False)
    return df


def faasr_adm1(
    influent_file: str = "digester_influent.csv",
    initial_file: str = "digester_initial.csv",
    output_file: str = "dynamic_out.csv",
    working_dir: str = ".",
    solver_method: str = "DOP853",
    # Reactor physical
    V_liq: float = 3400.0,
    V_gas: float = 300.0,
    T_op: float = 308.15,
    q_ad: float = 178.4674,
    # Disintegration / hydrolysis
    f_sI_xc: float = 0.1,
    f_xI_xc: float = 0.2,
    f_ch_xc: float = 0.2,
    f_pr_xc: float = 0.2,
    f_li_xc: float = 0.3,
    f_fa_li: float = 0.95,
    k_dis: float = 0.5,
    k_hyd_ch: float = 10.0,
    k_hyd_pr: float = 10.0,
    k_hyd_li: float = 10.0,
    # Biomass yields
    Y_su: float = 0.1,
    Y_aa: float = 0.08,
    Y_fa: float = 0.06,
    Y_c4: float = 0.06,
    Y_pro: float = 0.04,
    Y_ac: float = 0.05,
    Y_h2: float = 0.06,
    # Monod uptake kinetics
    k_m_su: float = 30.0, K_S_su: float = 0.5,
    k_m_aa: float = 50.0, K_S_aa: float = 0.3,
    k_m_fa: float = 6.0, K_S_fa: float = 0.4,
    k_m_c4: float = 20.0, K_S_c4: float = 0.2,
    k_m_pro: float = 13.0, K_S_pro: float = 0.1,
    k_m_ac: float = 8.0, K_S_ac: float = 0.15,
    k_m_h2: float = 35.0, K_S_h2: float = 7e-6,
    K_S_IN: float = 1e-4,
    # H2 and NH3 inhibition
    K_I_h2_fa: float = 5e-6,
    K_I_h2_c4: float = 1e-5,
    K_I_h2_pro: float = 3.5e-6,
    K_I_nh3: float = 0.0018,
    # pH inhibition windows
    pH_UL_aa: float = 5.5, pH_LL_aa: float = 4.0,
    pH_UL_ac: float = 7.0, pH_LL_ac: float = 6.0,
    pH_UL_h2: float = 6.0, pH_LL_h2: float = 5.0,
    # Decay rates
    k_dec_X_su: float = 0.02,
    k_dec_X_aa: float = 0.02,
    k_dec_X_fa: float = 0.02,
    k_dec_X_c4: float = 0.02,
    k_dec_X_pro: float = 0.02,
    k_dec_X_ac: float = 0.02,
    k_dec_X_h2: float = 0.02,
):
    """ADM1 anaerobic digester simulation.

    Reads ``influent_file`` and ``initial_file`` from ``working_dir`` and writes
    the state trajectory CSV to ``working_dir/output_file``. The exposed keyword
    arguments are the parameters most commonly calibrated against physical
    reactor observations (kinetic rates, half-saturations, biomass yields,
    inhibition constants, pH inhibition windows, decay rates, and reactor
    physical constants). All defaults are the BSM2 values from Rosen et al.
    (2006).
    """
    params = dict(
        V_liq=V_liq, V_gas=V_gas, T_op=T_op, q_ad=q_ad,
        f_sI_xc=f_sI_xc, f_xI_xc=f_xI_xc, f_ch_xc=f_ch_xc, f_pr_xc=f_pr_xc,
        f_li_xc=f_li_xc, f_fa_li=f_fa_li,
        k_dis=k_dis, k_hyd_ch=k_hyd_ch, k_hyd_pr=k_hyd_pr, k_hyd_li=k_hyd_li,
        Y_su=Y_su, Y_aa=Y_aa, Y_fa=Y_fa, Y_c4=Y_c4, Y_pro=Y_pro, Y_ac=Y_ac, Y_h2=Y_h2,
        k_m_su=k_m_su, K_S_su=K_S_su,
        k_m_aa=k_m_aa, K_S_aa=K_S_aa,
        k_m_fa=k_m_fa, K_S_fa=K_S_fa,
        k_m_c4=k_m_c4, K_S_c4=K_S_c4,
        k_m_pro=k_m_pro, K_S_pro=K_S_pro,
        k_m_ac=k_m_ac, K_S_ac=K_S_ac,
        k_m_h2=k_m_h2, K_S_h2=K_S_h2,
        K_S_IN=K_S_IN,
        K_I_h2_fa=K_I_h2_fa, K_I_h2_c4=K_I_h2_c4, K_I_h2_pro=K_I_h2_pro, K_I_nh3=K_I_nh3,
        pH_UL_aa=pH_UL_aa, pH_LL_aa=pH_LL_aa,
        pH_UL_ac=pH_UL_ac, pH_LL_ac=pH_LL_ac,
        pH_UL_h2=pH_UL_h2, pH_LL_h2=pH_LL_h2,
        k_dec_X_su=k_dec_X_su, k_dec_X_aa=k_dec_X_aa, k_dec_X_fa=k_dec_X_fa,
        k_dec_X_c4=k_dec_X_c4, k_dec_X_pro=k_dec_X_pro,
        k_dec_X_ac=k_dec_X_ac, k_dec_X_h2=k_dec_X_h2,
    )

    influent_path = os.path.join(working_dir, influent_file)
    initial_path = os.path.join(working_dir, initial_file)
    output_path = os.path.join(working_dir, output_file)

    df = _run_simulation(influent_path, initial_path, output_path, solver_method, params)
    print(f"ADM1 simulation finished: {len(df)} timesteps -> {output_path}")
    return output_path


def run_adm1(k_m_ac: float = 8.0, Y_ac: float = 0.05, k_dis: float = 0.5):
    rank = faasr_rank()["rank"]
    here = os.path.dirname(os.path.abspath(__file__))
    output_name = f"run_{rank}.csv"

    faasr_log(
        f"Rank {rank}: ADM1 with k_m_ac={k_m_ac:.4f}, Y_ac={Y_ac:.4f}, k_dis={k_dis:.4f}"
    )
    faasr_adm1(
        working_dir=here,
        output_file=output_name,
        k_m_ac=k_m_ac,
        Y_ac=Y_ac,
        k_dis=k_dis,
    )

    faasr_put_file(
        local_file=output_name,
        remote_file=output_name,
        local_folder=here,
        remote_folder=f"adm1-demo/{faasr_invocation_id()}/runs",
    )


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    faasr_adm1(working_dir=here, output_file="faasr_dynamic_out.csv")
