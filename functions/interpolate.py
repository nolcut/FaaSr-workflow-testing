def interpolate(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import tempfile, os

    EPOCH = "2000-01-01"  # arbitrary base date for constructing DatetimeIndex from fractional days

    local_in = tempfile.mktemp(suffix=".csv")
    local_out = tempfile.mktemp(suffix=".csv")

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"interpolate: read {input1} from {folder}")

    df = pd.read_csv(local_in)

    # Convert fractional-day time column to a DatetimeIndex
    base = pd.Timestamp(EPOCH)
    df.index = base + pd.to_timedelta(df["time"], unit="D")
    df.index.name = "datetime"

    # Build a complete, uniform 15-min DatetimeIndex covering the full range
    full_idx = pd.date_range(
        start=df.index.min(),
        end=df.index.max(),
        freq="15min",
    )

    # Reindex to the uniform 15-min grid
    df_reindexed = df.reindex(full_idx)

    # Identify the two high-frequency sensor columns
    sensor_cols = ["Q", "T (F)"]
    # Lab columns: everything except the time column and the sensor columns
    lab_cols = [c for c in df.columns if c != "time" and c not in sensor_cols]

    # Interpolate lab columns (time-weighted linear) to fill weekly gaps
    df_reindexed[lab_cols] = (
        df_reindexed[lab_cols]
        .interpolate(method="time")
        .ffill()
        .bfill()
    )

    # Sensor columns: forward-fill any NaNs introduced by reindex (should be none in practice)
    df_reindexed[sensor_cols] = df_reindexed[sensor_cols].ffill().bfill()

    # Reconstruct the fractional-day time column from the DatetimeIndex
    df_reindexed["time"] = (df_reindexed.index - base).total_seconds() / 86400.0

    # Restore original column order and drop the datetime index
    original_cols = list(df.columns)
    df_out = df_reindexed[original_cols].reset_index(drop=True)

    faasr_log(
        f"interpolate: rows {len(df)} -> {len(df_out)}, "
        f"NaN remaining={int(df_out.isna().sum().sum())}"
    )

    df_out.to_csv(local_out, index=False)
    faasr_log(f"interpolate: writing {output1} to {folder}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    os.remove(local_in)
    os.remove(local_out)
    faasr_log("interpolate: done")
