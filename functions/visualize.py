import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import tempfile
import os

def visualize(folder: str, input1: str, output1: str) -> None:
    faasr_log("visualize: starting")

    with tempfile.TemporaryDirectory() as tmp:
        local_in = os.path.join(tmp, "dynamic_out.csv")
        local_out = os.path.join(tmp, "simulation_plots.png")

        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
        df = pd.read_csv(local_in)
        faasr_log(f"visualize: loaded {len(df)} rows, {len(df.columns)} columns")

        # Time axis: row index in 15-min steps, converted to days
        t = np.arange(len(df)) / 96.0  # 96 steps per day

        fig, axes = plt.subplots(3, 2, figsize=(14, 12))
        fig.suptitle("PyADM1 Dynamic Simulation Results", fontsize=14, fontweight='bold')

        # Panel 1 — pH
        ax = axes[0, 0]
        ax.plot(t, df['pH'], color='steelblue', linewidth=1)
        ax.set_title('Reactor pH')
        ax.set_ylabel('pH')
        ax.set_xlabel('Time (days)')
        ax.grid(True, alpha=0.3)

        # Panel 2 — Gas phase concentrations
        ax = axes[0, 1]
        ax.plot(t, df['S_gas_ch4'], label='S_gas_ch4 (CH₄)', color='green', linewidth=1)
        ax.plot(t, df['S_gas_co2'], label='S_gas_co2 (CO₂)', color='orange', linewidth=1)
        ax.plot(t, df['S_gas_h2'],  label='S_gas_h2  (H₂)',  color='red',    linewidth=1)
        ax.set_title('Gas Phase Concentrations')
        ax.set_ylabel('kg COD/m³ or kmol C/m³')
        ax.set_xlabel('Time (days)')
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

        # Panel 3 — VFAs (volatile fatty acids)
        ax = axes[1, 0]
        for col, lbl, clr in [
            ('S_ac',  'Acetate (S_ac)',   'tab:blue'),
            ('S_pro', 'Propionate (S_pro)', 'tab:orange'),
            ('S_bu',  'Butyrate (S_bu)',   'tab:green'),
            ('S_va',  'Valerate (S_va)',   'tab:red'),
        ]:
            ax.plot(t, df[col], label=lbl, color=clr, linewidth=1)
        ax.set_title('Volatile Fatty Acids (VFAs)')
        ax.set_ylabel('kg COD/m³')
        ax.set_xlabel('Time (days)')
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

        # Panel 4 — Soluble COD fractions
        ax = axes[1, 1]
        for col, lbl, clr in [
            ('S_su', 'Sugars (S_su)',     'tab:blue'),
            ('S_aa', 'Amino acids (S_aa)', 'tab:orange'),
            ('S_fa', 'LCFA (S_fa)',        'tab:green'),
            ('S_I',  'Soluble inerts (S_I)', 'tab:purple'),
        ]:
            ax.plot(t, df[col], label=lbl, color=clr, linewidth=1)
        ax.set_title('Soluble COD Fractions')
        ax.set_ylabel('kg COD/m³')
        ax.set_xlabel('Time (days)')
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

        # Panel 5 — Particulate COD fractions
        ax = axes[2, 0]
        for col, lbl, clr in [
            ('X_ch',  'Carbohydrates (X_ch)', 'tab:blue'),
            ('X_pr',  'Proteins (X_pr)',       'tab:orange'),
            ('X_li',  'Lipids (X_li)',          'tab:green'),
            ('X_xc',  'Composites (X_xc)',      'tab:red'),
        ]:
            ax.plot(t, df[col], label=lbl, color=clr, linewidth=1)
        ax.set_title('Particulate COD Fractions')
        ax.set_ylabel('kg COD/m³')
        ax.set_xlabel('Time (days)')
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

        # Panel 6 — Inorganic carbon & nitrogen
        ax = axes[2, 1]
        ax2 = ax.twinx()
        l1, = ax.plot(t, df['S_IC'], label='S_IC (inorg. carbon)', color='tab:blue', linewidth=1)
        l2, = ax2.plot(t, df['S_IN'], label='S_IN (inorg. nitrogen)', color='tab:red',  linewidth=1, linestyle='--')
        ax.set_title('Inorganic Carbon & Nitrogen')
        ax.set_ylabel('kmol C/m³', color='tab:blue')
        ax2.set_ylabel('kmol N/m³', color='tab:red')
        ax.set_xlabel('Time (days)')
        ax.tick_params(axis='y', labelcolor='tab:blue')
        ax2.tick_params(axis='y', labelcolor='tab:red')
        lines = [l1, l2]
        ax.legend(lines, [l.get_label() for l in lines], fontsize=7)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        fig.savefig(local_out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        faasr_log(f"visualize: figure saved ({os.path.getsize(local_out)} bytes)")

        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
        faasr_log("visualize: done")
