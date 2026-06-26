def compute_monthly_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    faasr_get_file(local_file="oregon_temperature_january_2026.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("oregon_temperature_january_2026.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'oregon_temperature_january_2026.csv' must exist locally after download from S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_january_2026.csv") or os.path.getsize("oregon_temperature_january_2026.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'oregon_temperature_january_2026.csv' must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_temperature_january_2026.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'oregon_temperature_january_2026.csv' must be a valid CSV with at least two columns (date-like and numeric temperature-like) ({_e})")
        raise SystemExit(1)
    if not (at_least_one_numeric_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one numeric column usable as a temperature column")
        raise SystemExit(1)
    if not (date_column_parseable):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The date column in the input CSV must be parseable as datetime by pandas")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw Oregon temperature CSV from S3")

    df = pd.read_csv("oregon_temperature_january_2026.csv")
    faasr_log(f"Loaded {len(df)} rows from raw temperature file")

    # Identify date and temperature columns (case-insensitive)
    df.columns = df.columns.str.strip()
    col_lower = {c.lower(): c for c in df.columns}

    date_col = None
    for candidate in ["date", "datetime", "time", "day"]:
        if candidate in col_lower:
            date_col = col_lower[candidate]
            break
    if date_col is None:
        date_col = df.columns[0]
        faasr_log(f"No explicit date column found; using first column '{date_col}' as date")

    temp_col = None
    for candidate in ["temperature", "temp", "temperature_f", "temperature_c", "avg_temp", "tmax", "tmin", "tavg"]:
        if candidate in col_lower:
            temp_col = col_lower[candidate]
            break
    if temp_col is None:
        # Use the first numeric column that is not the date column
        for c in df.columns:
            if c != date_col and pd.api.types.is_numeric_dtype(df[c]):
                temp_col = c
                break
    if temp_col is None:
        temp_col = df.columns[1]
        faasr_log(f"No explicit temperature column found; using second column '{temp_col}' as temperature")

    faasr_log(f"Using date column: '{date_col}', temperature column: '{temp_col}'")

    df[date_col] = pd.to_datetime(df[date_col], infer_datetime_format=True)
    df["month"] = df[date_col].dt.to_period("M").astype(str)

    monthly_avg = (
        df.groupby("month")[temp_col]
        .mean()
        .reset_index()
        .rename(columns={temp_col: "average_temperature"})
    )
    monthly_avg = monthly_avg.sort_values("month").reset_index(drop=True)

    faasr_log(f"Computed monthly averages for {len(monthly_avg)} month(s)")

    monthly_avg.to_csv("oregon_monthly_avg_temperature.csv", index=False)
    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperature.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'oregon_monthly_avg_temperature.csv' must exist locally after processing")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperature.csv") or os.path.getsize("oregon_monthly_avg_temperature.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'oregon_monthly_avg_temperature.csv' must not be empty")
        raise SystemExit(1)
    # FORMAT check for csv_with_columns:month,average_temperature on oregon_monthly_avg_temperature.csv (not yet implemented)
    if not (month_column_sorted_ascending):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'month' column must be sorted in ascending order")
        raise SystemExit(1)
    if not (average_temperature_column_numeric):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'average_temperature' column must contain only numeric (float/int) values")
        raise SystemExit(1)
    if not (row_count_geq_1):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain at least one row of monthly average data")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_temperature_january_2026.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="oregon_monthly_avg_temperature.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded monthly average temperature CSV to S3")