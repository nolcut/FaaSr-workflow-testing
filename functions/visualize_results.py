import os
import tempfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "adm1_simulation_results.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: ADM1 simulation results CSV must exist in S3 before visualization can proceed")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "biogas_production_rate.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Biogas production rate plot PNG was not found in S3 after visualization")
        raise SystemExit(1)
    if "methane_composition.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Methane composition plot PNG was not found in S3 after visualization")
        raise SystemExit(1)
    if "effluent_concentrations.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Effluent concentrations plot PNG was not found in S3 after visualization")
        raise SystemExit(1)
    if "ph_alkalinity.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: pH and alkalinity plot PNG was not found in S3 after visualization")
        raise SystemExit(1)
# --- end contract helpers ---


def visualize_results(
    folder: str,
    input1: str,
    output1: str,
    output2: str,
    output3: str,
    output4: str,
) -> None:
    """Read ADM1 simulation results CSV and generate four publication-quality plots.

    Parameters
    ----------
    folder  : S3 folder (remote_folder for FaaSr calls)
    input1  : remote filename of the ADM1 simulation results CSV
    output1 : remote filename for biogas production rate plot (PNG)
    output2 : remote filename for methane composition plot (PNG)
    output3 : remote filename for effluent concentrations plot (PNG)
    output4 : remote filename for pH and alkalinity plot (PNG)
    """

    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    with tempfile.TemporaryDirectory() as tmpdir:
        local_csv = os.path.join(tmpdir, "adm1_simulation_results.csv")

        # ------------------------------------------------------------------
        # 1. Download simulation results
        # ------------------------------------------------------------------
        faasr_log(f"Downloading simulation results '{input1}' from folder '{folder}'")
        faasr_get_file(local_file=local_csv, remote_folder=folder, remote_file=input1)

        # ------------------------------------------------------------------
        # 2. Parse CSV
        # ------------------------------------------------------------------
        faasr_log("Parsing ADM1 simulation results CSV")
        try:
            df = pd.read_csv(local_csv)
        except Exception as e:
            faasr_log(f"ERROR: failed to parse simulation results CSV: {e}")
            raise

        faasr_log(f"Loaded DataFrame: {df.shape[0]} rows x {df.shape[1]} columns")
        faasr_log(f"Columns: {df.columns.tolist()}")

        # Validate required columns are present
        required_cols = [
            "time", "q_gas",
            "p_gas_h2", "p_gas_ch4", "p_gas_co2",
            "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac",
            "S_IC", "S_IN", "S_I",
            "X_xc", "X_ch", "X_pr", "X_li", "X_I",
            "S_hco3_ion", "S_nh3", "S_nh4_ion",
            "pH",
        ]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            msg = f"Simulation results CSV is missing required columns: {missing}"
            faasr_log(f"ERROR: {msg}")
            raise ValueError(msg)

        t = df["time"].values

        # ------------------------------------------------------------------
        # 3. Plot 1: Biogas production rate over time
        # ------------------------------------------------------------------
        faasr_log("Generating biogas production rate plot")
        local_p1 = os.path.join(tmpdir, output1)

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(t, df["q_gas"].values, color="steelblue", linewidth=1.5, label="Total biogas flow")
        ax.set_xlabel("Time (days)", fontsize=13)
        ax.set_ylabel(r"Biogas production rate (m$^3$ d$^{-1}$)", fontsize=13)
        ax.set_title("ADM1: Biogas Production Rate", fontsize=14, fontweight="bold")
        ax.legend(fontsize=11)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.set_xlim(left=t[0], right=t[-1])
        fig.tight_layout()
        fig.savefig(local_p1, dpi=150)
        plt.close(fig)
        faasr_log(f"Saved biogas production rate plot to '{local_p1}'")

        # ------------------------------------------------------------------
        # 4. Plot 2: Methane composition in biogas
        # ------------------------------------------------------------------
        faasr_log("Generating methane composition plot")
        local_p2 = os.path.join(tmpdir, output2)

        p_h2  = df["p_gas_h2"].values
        p_ch4 = df["p_gas_ch4"].values
        p_co2 = df["p_gas_co2"].values
        p_tot = p_h2 + p_ch4 + p_co2
        # Guard against division by zero (if biogas is not yet produced)
        with np.errstate(invalid="ignore", divide="ignore"):
            frac_ch4 = np.where(p_tot > 0, p_ch4 / p_tot * 100.0, np.nan)
            frac_co2 = np.where(p_tot > 0, p_co2 / p_tot * 100.0, np.nan)
            frac_h2  = np.where(p_tot > 0, p_h2  / p_tot * 100.0, np.nan)

        fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True)

        # Upper panel: partial pressures
        ax = axes[0]
        ax.plot(t, p_ch4, color="forestgreen",  linewidth=1.5, label=r"p$_{\rm CH_4}$ (bar)")
        ax.plot(t, p_co2, color="firebrick",    linewidth=1.5, label=r"p$_{\rm CO_2}$ (bar)")
        ax.plot(t, p_h2,  color="darkorange",   linewidth=1.5, label=r"p$_{\rm H_2}$ (bar)")
        ax.set_ylabel("Partial pressure (bar)", fontsize=12)
        ax.set_title("ADM1: Biogas Composition", fontsize=14, fontweight="bold")
        ax.legend(fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.5)

        # Lower panel: mole fractions
        ax = axes[1]
        ax.plot(t, frac_ch4, color="forestgreen", linewidth=1.5, label=r"CH$_4$ (%)")
        ax.plot(t, frac_co2, color="firebrick",   linewidth=1.5, label=r"CO$_2$ (%)")
        ax.plot(t, frac_h2,  color="darkorange",  linewidth=1.5, label=r"H$_2$ (%)")
        ax.set_xlabel("Time (days)", fontsize=12)
        ax.set_ylabel("Mole fraction (%)", fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.set_xlim(left=t[0], right=t[-1])

        fig.tight_layout()
        fig.savefig(local_p2, dpi=150)
        plt.close(fig)
        faasr_log(f"Saved methane composition plot to '{local_p2}'")

        # ------------------------------------------------------------------
        # 5. Plot 3: Multi-panel effluent concentrations
        # ------------------------------------------------------------------
        faasr_log("Generating effluent concentrations plot")
        local_p3 = os.path.join(tmpdir, output3)

        fig = plt.figure(figsize=(14, 12))
        fig.suptitle("ADM1: Key Effluent Concentrations", fontsize=15, fontweight="bold", y=0.98)
        gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.35)

        # Panel A: Volatile Fatty Acids (VFAs)
        ax_a = fig.add_subplot(gs[0, 0])
        ax_a.plot(t, df["S_va"].values,  color="tab:purple", linewidth=1.4, label=r"S$_{\rm va}$ (valerate)")
        ax_a.plot(t, df["S_bu"].values,  color="tab:orange", linewidth=1.4, label=r"S$_{\rm bu}$ (butyrate)")
        ax_a.plot(t, df["S_pro"].values, color="tab:red",    linewidth=1.4, label=r"S$_{\rm pro}$ (propionate)")
        ax_a.plot(t, df["S_ac"].values,  color="tab:green",  linewidth=1.4, label=r"S$_{\rm ac}$ (acetate)")
        ax_a.set_title("(A) Volatile Fatty Acids", fontsize=12, fontweight="bold")
        ax_a.set_ylabel(r"Concentration (kg COD m$^{-3}$)", fontsize=10)
        ax_a.set_xlabel("Time (days)", fontsize=10)
        ax_a.legend(fontsize=8, loc="best")
        ax_a.grid(True, linestyle="--", alpha=0.5)

        # Panel B: Soluble COD fractions
        ax_b = fig.add_subplot(gs[0, 1])
        ax_b.plot(t, df["S_su"].values, color="tab:blue",   linewidth=1.4, label=r"S$_{\rm su}$ (sugars)")
        ax_b.plot(t, df["S_aa"].values, color="tab:cyan",   linewidth=1.4, label=r"S$_{\rm aa}$ (amino acids)")
        ax_b.plot(t, df["S_fa"].values, color="tab:brown",  linewidth=1.4, label=r"S$_{\rm fa}$ (LCFA)")
        ax_b.plot(t, df["S_I"].values,  color="tab:gray",   linewidth=1.4, label=r"S$_{\rm I}$ (inert)")
        ax_b.set_title("(B) Soluble COD Fractions", fontsize=12, fontweight="bold")
        ax_b.set_ylabel(r"Concentration (kg COD m$^{-3}$)", fontsize=10)
        ax_b.set_xlabel("Time (days)", fontsize=10)
        ax_b.legend(fontsize=8, loc="best")
        ax_b.grid(True, linestyle="--", alpha=0.5)

        # Panel C: Particulate COD fractions
        ax_c = fig.add_subplot(gs[1, 0])
        ax_c.plot(t, df["X_xc"].values, color="saddlebrown",  linewidth=1.4, label=r"X$_{\rm xc}$ (composites)")
        ax_c.plot(t, df["X_ch"].values, color="goldenrod",    linewidth=1.4, label=r"X$_{\rm ch}$ (carbohydrates)")
        ax_c.plot(t, df["X_pr"].values, color="mediumpurple", linewidth=1.4, label=r"X$_{\rm pr}$ (proteins)")
        ax_c.plot(t, df["X_li"].values, color="coral",        linewidth=1.4, label=r"X$_{\rm li}$ (lipids)")
        ax_c.plot(t, df["X_I"].values,  color="slategray",    linewidth=1.4, label=r"X$_{\rm I}$ (inert)")
        ax_c.set_title("(C) Particulate COD Fractions", fontsize=12, fontweight="bold")
        ax_c.set_ylabel(r"Concentration (kg COD m$^{-3}$)", fontsize=10)
        ax_c.set_xlabel("Time (days)", fontsize=10)
        ax_c.legend(fontsize=8, loc="best")
        ax_c.grid(True, linestyle="--", alpha=0.5)

        # Panel D: Inorganic nitrogen species
        ax_d = fig.add_subplot(gs[1, 1])
        ax_d.plot(t, df["S_IN"].values,     color="teal",       linewidth=1.4, label=r"S$_{\rm IN}$ (total inorg. N)")
        ax_d.plot(t, df["S_nh4_ion"].values, color="steelblue",  linewidth=1.4, label=r"S$_{\rm NH_4^+}$")
        ax_d.plot(t, df["S_nh3"].values,    color="darkorchid", linewidth=1.4, label=r"S$_{\rm NH_3}$ (free ammonia)")
        ax_d.set_title("(D) Nitrogen Species", fontsize=12, fontweight="bold")
        ax_d.set_ylabel(r"Concentration (kmol N m$^{-3}$)", fontsize=10)
        ax_d.set_xlabel("Time (days)", fontsize=10)
        ax_d.legend(fontsize=8, loc="best")
        ax_d.grid(True, linestyle="--", alpha=0.5)

        for ax in [ax_a, ax_b, ax_c, ax_d]:
            ax.set_xlim(left=t[0], right=t[-1])

        fig.savefig(local_p3, dpi=150, bbox_inches="tight")
        plt.close(fig)
        faasr_log(f"Saved effluent concentrations plot to '{local_p3}'")

        # ------------------------------------------------------------------
        # 6. Plot 4: pH and bicarbonate alkalinity
        # ------------------------------------------------------------------
        faasr_log("Generating pH and alkalinity plot")
        local_p4 = os.path.join(tmpdir, output4)

        # Bicarbonate alkalinity: S_hco3_ion in kmol/m³ → convert to mmol/L (= mol/m³)
        # 1 kmol/m³ = 1000 mol/m³ = 1000 mmol/L
        alk_mM = df["S_hco3_ion"].values * 1000.0  # mmol/L

        fig, ax1 = plt.subplots(figsize=(9, 5))

        color_pH  = "royalblue"
        color_alk = "darkorange"

        ln1 = ax1.plot(t, df["pH"].values, color=color_pH, linewidth=1.8, label="pH")
        ax1.set_xlabel("Time (days)", fontsize=13)
        ax1.set_ylabel("pH", color=color_pH, fontsize=13)
        ax1.tick_params(axis="y", labelcolor=color_pH)
        ax1.set_ylim(
            max(0.0, df["pH"].values.min() - 0.5),
            min(14.0, df["pH"].values.max() + 0.5),
        )
        ax1.grid(True, linestyle="--", alpha=0.4)

        ax2 = ax1.twinx()
        ln2 = ax2.plot(t, alk_mM, color=color_alk, linewidth=1.8,
                       linestyle="--", label="Alkalinity (HCO₃⁻)")
        ax2.set_ylabel(r"Bicarbonate alkalinity (mmol L$^{-1}$)", color=color_alk, fontsize=13)
        ax2.tick_params(axis="y", labelcolor=color_alk)

        ax1.set_xlim(left=t[0], right=t[-1])
        ax1.set_title("ADM1: pH and Bicarbonate Alkalinity", fontsize=14, fontweight="bold")

        lns = ln1 + ln2
        labs = [ln.get_label() for ln in lns]
        ax1.legend(lns, labs, fontsize=11, loc="best")

        fig.tight_layout()
        fig.savefig(local_p4, dpi=150)
        plt.close(fig)
        faasr_log(f"Saved pH and alkalinity plot to '{local_p4}'")

        # ------------------------------------------------------------------
        # 7. Upload all plots to S3
        # ------------------------------------------------------------------
        faasr_log(f"Uploading '{output1}' to folder '{folder}'")
        faasr_put_file(local_file=local_p1, remote_folder=folder, remote_file=output1)

        faasr_log(f"Uploading '{output2}' to folder '{folder}'")
        faasr_put_file(local_file=local_p2, remote_folder=folder, remote_file=output2)

        faasr_log(f"Uploading '{output3}' to folder '{folder}'")
        faasr_put_file(local_file=local_p3, remote_folder=folder, remote_file=output3)

        faasr_log(f"Uploading '{output4}' to folder '{folder}'")
        faasr_put_file(local_file=local_p4, remote_folder=folder, remote_file=output4)

        faasr_log("visualize_results complete: all four plots uploaded successfully")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---