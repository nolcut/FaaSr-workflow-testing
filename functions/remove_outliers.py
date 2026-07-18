def remove_outliers(folder: str, input1: str, output1: str) -> None:
    """Fifth (final) step of the PyADM1 digester preprocessing pipeline.

    Reads the gap-filled influent CSV (input1) from the S3 folder, detects and
    removes outlier spikes in the flow column 'Q' and the temperature column
    'T (C)' using a robust rolling-window (Hampel) filter, and replaces each
    detected spike with the local median of the surrounding values. All other
    columns, the row order, and the DataFrame index are preserved. The cleaned
    result is written to output1 ('digester_influent.csv'), the filename the
    PyADM1 simulation code reads.
    """
    import pandas as pd
    import numpy as np

    local_in = "influent_gaps_filled.csv"
    local_out = "digester_influent.csv"

    faasr_log(f"remove_outliers: fetching '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    target_cols = ["Q", "T (C)"]
    missing = [c for c in target_cols if c not in df.columns]
    if missing:
        msg = (
            f"remove_outliers: expected column(s) {missing} not found in "
            f"'{input1}'. Columns present: {list(df.columns)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Hampel filter parameters: a centered rolling window and a robust
    # (median absolute deviation) threshold. 1.4826 scales the MAD to be a
    # consistent estimator of the standard deviation for normally distributed
    # data; a point is a spike if it deviates from the local median by more than
    # n_sigmas robust standard deviations.
    window = 7
    n_sigmas = 3.0
    mad_scale = 1.4826

    for col in target_cols:
        series = pd.to_numeric(df[col], errors="raise").astype(float)
        rolling_median = series.rolling(window, center=True, min_periods=1).median()
        abs_dev = (series - rolling_median).abs()
        rolling_mad = abs_dev.rolling(window, center=True, min_periods=1).median()
        threshold = n_sigmas * mad_scale * rolling_mad
        outliers = abs_dev > threshold

        n_out = int(outliers.sum())
        # Replace detected spikes with the local (rolling) median.
        series[outliers] = rolling_median[outliers]
        df[col] = series
        faasr_log(
            f"remove_outliers: replaced {n_out} outlier spike(s) in '{col}' "
            f"with the local median"
        )

    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"remove_outliers: wrote cleaned influent to '{output1}'")
