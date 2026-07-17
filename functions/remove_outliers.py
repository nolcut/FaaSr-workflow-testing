def remove_outliers(folder: str, input1: str, output1: str) -> None:
    import numpy as np
    import pandas as pd

    local_in = "influent_gaps_filled.csv"
    local_out = "influent_outliers_removed.csv"

    faasr_log(f"remove_outliers: fetching {input1} from folder {folder}")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    target_cols = ["Q", "T (C)"]
    missing = [c for c in target_cols if c not in df.columns]
    if missing:
        msg = (
            f"remove_outliers: required column(s) {missing} not found in {input1}; "
            f"columns present: {list(df.columns)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Robust spike detection: for each target column compute a centered rolling
    # median and the rolling median absolute deviation (MAD). A point whose
    # deviation from the local median exceeds K * scaled-MAD is flagged as an
    # outlier and replaced by that local median. Where MAD is degenerate (0),
    # fall back to a rolling-standard-deviation threshold.
    window = 7          # neighboring rows used for the local statistics
    k = 5.0             # threshold as a multiple of the robust spread
    mad_scale = 1.4826  # scales MAD to be consistent with the std of a normal dist

    for col in target_cols:
        series = pd.to_numeric(df[col], errors="coerce")

        med = series.rolling(window, center=True, min_periods=1).median()
        abs_dev = (series - med).abs()
        mad = abs_dev.rolling(window, center=True, min_periods=1).median()
        scaled_mad = mad_scale * mad

        std = series.rolling(window, center=True, min_periods=1).std()

        # Use the MAD-based threshold where the local spread is non-degenerate,
        # otherwise fall back to the std-based threshold.
        threshold = (k * scaled_mad).where(scaled_mad > 0, k * std)

        # Only rows with a meaningful (finite, positive) threshold can flag outliers.
        valid = threshold.notna() & (threshold > 0)
        is_outlier = valid & (abs_dev > threshold)

        n_out = int(is_outlier.sum())
        if n_out:
            df.loc[is_outlier, col] = med[is_outlier]
        faasr_log(
            f"remove_outliers: column '{col}' — replaced {n_out} spike(s) with local median "
            f"(window={window}, k={k})"
        )

    df.to_csv(local_out, index=False)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"remove_outliers: wrote {output1} to folder {folder}")
