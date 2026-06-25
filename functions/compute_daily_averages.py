def compute_daily_averages(folder: str, raw_temperature: str, daily_averages: str) -> None:
    import pandas as pd

    faasr_get_file(local_file="raw_temperature.csv", remote_folder=folder, remote_file=raw_temperature)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("raw_temperature.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("raw_temperature.csv") or os.path.getsize("raw_temperature.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("raw_temperature.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_at_least_2_columns):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least two columns (one for date/time and one for temperature values)")
        raise SystemExit(1)
    if not (has_parseable_date_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one column that can be parsed as datetime values")
        raise SystemExit(1)
    if not (has_numeric_temperature_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one numeric column usable as temperature values")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw temperature data from S3")

    df = pd.read_csv("raw_temperature.csv")
    faasr_log(f"Loaded raw temperature data with {len(df)} rows and columns: {list(df.columns)}")

    # Try to identify the date/datetime column
    date_col = None
    for col in df.columns:
        if col.lower() in ("date", "datetime", "time", "timestamp"):
            date_col = col
            break
    if date_col is None:
        # Fall back to first column
        date_col = df.columns[0]
        faasr_log(f"No obvious date column found, using first column: {date_col}")

    # Try to identify the temperature column
    temp_col = None
    for col in df.columns:
        if col.lower() in ("temperature", "temp", "tmax", "tmin", "tavg", "value", "tmean"):
            temp_col = col
            break
    if temp_col is None:
        # Use the first numeric column that is not the date column
        for col in df.columns:
            if col != date_col and pd.api.types.is_numeric_dtype(df[col]):
                temp_col = col
                break
    if temp_col is None:
        temp_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        faasr_log(f"No obvious temperature column found, using column: {temp_col}")

    faasr_log(f"Using date column: '{date_col}', temperature column: '{temp_col}'")

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    # Filter to January 2026
    mask = (df[date_col].dt.year == 2026) & (df[date_col].dt.month == 1)
    df_jan = df.loc[mask].copy()
    faasr_log(f"Rows after filtering to January 2026: {len(df_jan)}")

    if df_jan.empty:
        faasr_log("Warning: No data found for January 2026; computing averages from full dataset instead")
        df_jan = df.copy()

    df_jan["date"] = df_jan[date_col].dt.date
    daily_avg = df_jan.groupby("date")[temp_col].mean().reset_index()
    daily_avg.columns = ["date", "avg_temperature"]
    daily_avg = daily_avg.sort_values("date").reset_index(drop=True)

    faasr_log(f"Computed daily averages for {len(daily_avg)} days")

    daily_avg.to_csv("daily_averages.csv", index=False)
    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("daily_averages.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file daily_averages.csv must exist after processing")
        raise SystemExit(1)
    if not os.path.exists("daily_averages.csv") or os.path.getsize("daily_averages.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file daily_averages.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("daily_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file daily_averages.csv must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_columns:date,avg_temperature):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain exactly the columns 'date' and 'avg_temperature'")
        raise SystemExit(1)
    if not (avg_temperature_column_is_numeric):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV column 'avg_temperature' must contain only numeric (float/int) values")
        raise SystemExit(1)
    if not (date_column_is_sorted_ascending):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must be sorted in ascending order by the 'date' column")
        raise SystemExit(1)
    if not (date_column_has_no_duplicates):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must have exactly one row per unique date (no duplicate dates)")
        raise SystemExit(1)
    if not (no_null_values):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain no null or NaN values in any column")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: raw_temperature.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=daily_averages)
    faasr_log("Uploaded daily averages CSV to S3")