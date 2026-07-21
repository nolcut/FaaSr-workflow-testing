def remove_spikes(folder: str, input1: str, output1: str) -> None:
    """Replace isolated sensor spikes in the Q and T columns with the local median.

    For each of Q and T a rolling median and a rolling median-absolute-deviation
    (MAD) are computed over a small local window. Points that deviate from their
    local median by more than a robust threshold (a multiple of the scaled MAD)
    are flagged as isolated spikes and replaced by the local median value. All
    other columns and every non-spike value are left untouched.
    """
    import pandas as pd
    import numpy as np

    WINDOW = 5          # small local window (odd, centered)
    THRESHOLD = 5.0     # deviation multiple of the robust scale to flag a spike
    MAD_SCALE = 1.4826  # makes MAD a consistent estimator of sigma for normal data

    faasr_log(f"remove_spikes: downloading gap-filled influent '{input1}' from folder '{folder}'")
    local_in = "influent_gapfilled.csv"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)
    faasr_log(f"remove_spikes: read {len(df)} rows, {len(df.columns)} columns")

    # Resolve the temperature column name (convert_units renamed 'T (F)' -> 'T (C)').
    temp_col = None
    for cand in ("T (C)", "T(C)", "T_C", "T (F)", "T"):
        if cand in df.columns:
            temp_col = cand
            break
    if temp_col is None:
        msg = "remove_spikes: could not find a temperature column (expected 'T (C)')"
        faasr_log(msg)
        raise ValueError(msg)
    if "Q" not in df.columns:
        msg = "remove_spikes: required flow column 'Q' not found in input CSV"
        faasr_log(msg)
        raise ValueError(msg)

    def despike(series):
        s = series.astype(float)
        # Detrend with a small centered rolling median (robust to isolated spikes).
        local_med = s.rolling(window=WINDOW, center=True, min_periods=1).median()
        abs_dev = (s - local_med).abs()
        # Robust noise scale = scaled median of the NON-ZERO residuals. On a nearly
        # noiseless smooth signal most residuals are exactly zero, which collapses a
        # plain MAD to zero; excluding the zeros yields a stable scale that reflects
        # ordinary curvature, so only genuinely isolated spikes exceed the threshold.
        # On a noisy signal most residuals are non-zero and this reduces to a MAD.
        nonzero = abs_dev[abs_dev > 0]
        if len(nonzero) == 0:
            # Perfectly flat/linear column — nothing to despike.
            return s, 0
        scale = MAD_SCALE * float(np.median(nonzero))
        if scale <= 0:
            return s, 0
        is_spike = abs_dev > (THRESHOLD * scale)
        out = s.mask(is_spike, local_med)
        return out, int(is_spike.sum())

    for col in ("Q", temp_col):
        df[col], n_spikes = despike(df[col])
        faasr_log(f"remove_spikes: {col} — replaced {n_spikes} isolated spike(s) with local median")

    local_out = "influent_despiked.csv"
    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"remove_spikes: wrote despiked influent '{output1}' to folder '{folder}'")
