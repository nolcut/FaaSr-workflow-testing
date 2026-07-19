def remove_outliers(folder: str, input1: str, output1: str) -> None:
    """De-spike the Q (flow) and T (C) columns of the influent data.

    Reads the cleaned influent CSV (input1) from the S3 folder. For each of the
    Q and 'T (C)' columns it applies a Hampel filter: a centered rolling local
    median and a centered rolling median-absolute-deviation (MAD). A value is
    flagged as an outlier spike when its deviation from the local median exceeds
    N_SIGMA * 1.4826 * MAD (a robust, locally-scaled threshold), and each flagged
    spike is replaced with the corresponding local median. Windows with zero MAD
    (e.g. constant stretches) flag nothing. All other columns are left unchanged.
    The de-spiked result is written back to output1 for downstream PyADM1
    simulation.
    """
    import os
    import numpy as np
    import pandas as pd

    local_in = "influent_in.csv"
    local_out = "influent_out.csv"

    WINDOW = 7            # centered rolling window
    N_SIGMA = 3.0         # robust threshold multiplier
    MAD_SCALE = 1.4826    # consistency constant: MAD -> std for normal data

    faasr_log(f"remove_outliers: fetching {input1} from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    target_cols = ["Q", "T (C)"]
    missing = [c for c in target_cols if c not in df.columns]
    if missing:
        msg = (f"remove_outliers: expected column(s) {missing} not found in "
               f"{input1}; columns are {list(df.columns)}")
        faasr_log(msg)
        raise ValueError(msg)

    def _mad(x):
        return np.median(np.abs(x - np.median(x)))

    for col in target_cols:
        series = df[col].astype(float)
        # require a full centered window: edge points (first/last WINDOW//2)
        # get NaN scale and are never flagged, so genuine endpoint values (e.g.
        # the documented initial flow rate) are not mistaken for spikes.
        local_med = series.rolling(window=WINDOW, center=True,
                                   min_periods=WINDOW).median()
        local_mad = series.rolling(window=WINDOW, center=True,
                                   min_periods=WINDOW).apply(_mad, raw=True)
        scale = MAD_SCALE * local_mad
        deviation = (series - local_med).abs()
        # only flag where there is robust local dispersion to measure against
        spike_mask = (scale > 0) & (deviation > N_SIGMA * scale)
        n_spikes = int(spike_mask.sum())
        faasr_log(f"remove_outliers: column '{col}' flagged {n_spikes} spike(s) "
                  f"over {len(df)} rows (window={WINDOW}, n_sigma={N_SIGMA})")
        if n_spikes:
            df.loc[spike_mask, col] = local_med[spike_mask]

    df.to_csv(local_out, index=False)

    faasr_log(f"remove_outliers: writing de-spiked influent to {output1}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    for f in (local_in, local_out):
        if os.path.exists(f):
            os.remove(f)

    faasr_log("remove_outliers: complete")
