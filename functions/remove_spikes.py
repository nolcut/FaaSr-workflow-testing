import pandas as pd
import numpy as np

# Columns cleaned for isolated sensor spikes. Q is the flow (m3/d after step 1),
# T_C is the temperature in Celsius (renamed in step 1).
SPIKE_COLUMNS = ["Q", "T_C"]

WINDOW = 5      # rolling window (odd, centered) for the local median
THRESHOLD = 5.0  # a point is a spike if its residual exceeds THRESHOLD * (1.4826*MAD)


def remove_spikes(folder="PyADM1-orig",
                  input_file="influent_step2_filled.csv",
                  output_file="influent_step3_despiked.csv"):
    """Step 3 - detect and replace isolated sensor spikes in BOTH Q and T_C
    with the local (rolling) median.

    A robust rolling-median / MAD filter flags points whose deviation from the
    local median is large, then replaces only those isolated points with the
    local median value (leaving the rest of the signal intact).
    """
    faasr_get_file(remote_folder=folder, remote_file=input_file, local_file="in.csv")
    df = pd.read_csv("in.csv")

    for col in SPIKE_COLUMNS:
        if col not in df.columns:
            faasr_log(f"remove_spikes WARNING: column '{col}' not found; skipping")
            continue

        s = df[col].astype(float)
        local_med = s.rolling(window=WINDOW, center=True, min_periods=1).median()
        residual = (s - local_med).abs()

        # Robust global scale via median absolute deviation.
        mad = np.median(np.abs(residual - np.median(residual)))
        scale = 1.4826 * mad if mad > 0 else residual.std(ddof=0)
        if not scale or np.isnan(scale):
            faasr_log(f"remove_spikes: '{col}' has no variability; nothing to do")
            continue

        spikes = residual > (THRESHOLD * scale)
        n_spikes = int(spikes.sum())
        df.loc[spikes, col] = local_med[spikes]
        faasr_log(f"remove_spikes: replaced {n_spikes} spike(s) in '{col}' with local median")

    df.to_csv("despiked.csv", index=False)
    faasr_put_file(local_file="despiked.csv", remote_folder=folder, remote_file=output_file)
    faasr_log(f"remove_spikes: wrote {folder}/{output_file}")
