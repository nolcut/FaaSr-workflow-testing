def visualize(folder: str, input1: str, output1: str) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import pandas as pd
    import tempfile, os

    local_in = tempfile.mktemp(suffix=".csv")
    local_out = tempfile.mktemp(suffix=".png")

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"visualize: read {input1} from {folder}")

    df = pd.read_csv(local_in)

    # Use row index as the time axis (simulation step)
    time = df.index

    fig, axes = plt.subplots(3, 1, figsize=(12, 12))

    # ── Panel 1: Gas-phase concentrations (proxy for biogas flow rates) ────────
    ax = axes[0]
    gas_cols = [c for c in ['S_gas_h2', 'S_gas_ch4', 'S_gas_co2'] if c in df.columns]
    labels = {'S_gas_h2': 'H₂ (kg COD/m³)', 'S_gas_ch4': 'CH₄ (kg COD/m³)', 'S_gas_co2': 'CO₂ (kmol C/m³)'}
    for col in gas_cols:
        ax.plot(time, df[col], label=labels.get(col, col))
    ax.set_title('Gas-Phase Concentrations (Biogas)')
    ax.set_xlabel('Simulation Step')
    ax.set_ylabel('Concentration')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.5)

    # ── Panel 2: Effluent soluble components ───────────────────────────────────
    ax = axes[1]
    soluble_cols = [c for c in ['S_su', 'S_ac', 'S_pro', 'S_bu'] if c in df.columns]
    sol_labels = {
        'S_su': 'S_su – sugars',
        'S_ac': 'S_ac – acetate',
        'S_pro': 'S_pro – propionate',
        'S_bu': 'S_bu – butyrate',
    }
    for col in soluble_cols:
        ax.plot(time, df[col], label=sol_labels.get(col, col))
    ax.set_title('Effluent Soluble Components (kg COD/m³)')
    ax.set_xlabel('Simulation Step')
    ax.set_ylabel('Concentration (kg COD/m³)')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.5)

    # ── Panel 3: pH ────────────────────────────────────────────────────────────
    ax = axes[2]
    if 'pH' in df.columns:
        ax.plot(time, df['pH'], color='tab:purple', label='pH')
        ax.set_ylabel('pH')
        ax.set_title('Reactor pH Over Simulation')
    elif 'S_H_ion' in df.columns:
        import numpy as np
        ax.plot(time, -np.log10(df['S_H_ion']), color='tab:purple', label='pH (derived)')
        ax.set_ylabel('pH')
        ax.set_title('Reactor pH Over Simulation')
    else:
        ax.text(0.5, 0.5, 'pH data not available', ha='center', va='center',
                transform=ax.transAxes)
        ax.set_title('pH')
    ax.set_xlabel('Simulation Step')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.5)

    fig.suptitle('PyADM1 Simulation Results', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(local_out, dpi=150, bbox_inches='tight')
    plt.close(fig)

    faasr_log(f"visualize: saved figure to {output1}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    os.remove(local_in)
    os.remove(local_out)
    faasr_log("visualize: done")
