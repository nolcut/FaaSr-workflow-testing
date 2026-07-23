# Step 3: remove-spikes
# Detect and replace ISOLATED sensor spikes in BOTH Q (flow) and T (temperature)
# with the local median. A rolling-median / MAD (modified z-score) detector flags
# single points that deviate strongly from their local neighbourhood; each flagged
# point is replaced by the local rolling median so surrounding good data is kept.

def remove_spikes(folder, input_file="influent_filled.csv",
                  output_file="influent_despiked.csv",
                  window=7, threshold=5.0):
    import pandas as pd
    import numpy as np

    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file=input_file)
    df = pd.read_csv(input_file)

    for col in ["Q", "T"]:
        if col not in df.columns:
            continue
        s = df[col].astype(float)
        # local median over a centred window (Hampel-style filter)
        med = s.rolling(window, center=True, min_periods=1).median()
        resid = s - med

        # GLOBAL robust scale of the residuals. Using the median-of-residuals
        # over the whole series (rather than a tiny rolling window) is stable:
        # a few isolated spikes barely move a median, so the scale reflects the
        # true noise level and normal fluctuations are not flagged.
        gmad = float((resid - resid.median()).abs().median())
        scale = 1.4826 * gmad

        if not np.isfinite(scale) or scale <= 0.0:
            # (nearly) constant sensor: any real deviation from the local median
            # is a spike. Tolerance is relative to the signal magnitude.
            tol = max(1e-9, 1e-3 * float(s.abs().median()))
            spikes = resid.abs() > tol
        else:
            spikes = (resid.abs() / scale) > threshold
        spikes = spikes & resid.notna()

        n = int(spikes.sum())
        df.loc[spikes, col] = med[spikes]
        faasr_log(f"remove_spikes: replaced {n} isolated spike(s) in '{col}' with local median")

    df.to_csv(output_file, index=False)
    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"remove_spikes: wrote {folder}/{output_file}")
