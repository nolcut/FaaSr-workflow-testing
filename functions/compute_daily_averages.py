def compute_daily_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    faasr_get_file(local_file="oregon_temp_raw.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("oregon_temp_raw.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file oregon_temp_raw.csv must exist on S3 and be downloadable")
        raise SystemExit(1)
    if not os.path.exists("oregon_temp_raw.csv") or os.path.getsize("oregon_temp_raw.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file oregon_temp_raw.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_temp_raw.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file oregon_temp_raw.csv must be a valid CSV file parseable by pandas ({_e})")
        raise SystemExit(1)
    if not (has_at_least_two_columns):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least two columns so a date column and a temperature column can be identified")
        raise SystemExit(1)
    if not (date_column_parseable_as_datetime):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The identified date/timestamp column in oregon_temp_raw.csv must be parseable by pd.to_datetime")
        raise SystemExit(1)
    if not (temperature_column_is_numeric):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The identified temperature column in oregon_temp_raw.csv must contain numeric values suitable for averaging")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw temperature data from S3")

    df = pd.read_csv("oregon_temp_raw.csv")
    faasr_log(f"Loaded raw data with {len(df)} records and columns: {list(df.columns)}")

    # Try to identify the datetime/date column and temperature column
    date_col = None
    temp_col = None

    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["date", "time", "datetime", "timestamp"]):
            date_col = col
            break

    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["temp", "temperature", "tmax", "tmin", "tavg", "value"]):
            temp_col = col
            break

    if date_col is None:
        date_col = df.columns[0]
        faasr_log(f"No date column found by name, using first column: {date_col}")

    if temp_col is None:
        # Pick the first numeric column that is not the date column
        for col in df.columns:
            if col != date_col and pd.api.types.is_numeric_dtype(df[col]):
                temp_col = col
                break
        if temp_col is None:
            temp_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        faasr_log(f"No temperature column found by name, using column: {temp_col}")

    faasr_log(f"Using date column: '{date_col}', temperature column: '{temp_col}'")

    df[date_col] = pd.to_datetime(df[date_col])

    # Filter to January 2026
    jan2026_mask = (df[date_col].dt.year == 2026) & (df[date_col].dt.month == 1)
    df_jan = df[jan2026_mask].copy()

    if df_jan.empty:
        faasr_log("Warning: No records found for January 2026; using all available data")
        df_jan = df.copy()

    faasr_log(f"Records for January 2026: {len(df_jan)}")

    df_jan["date"] = df_jan[date_col].dt.date
    daily_avg = df_jan.groupby("date")[temp_col].mean().reset_index()
    daily_avg.columns = ["date", "avg_temperature"]
    daily_avg = daily_avg.sort_values("date").reset_index(drop=True)

    faasr_log(f"Computed daily averages for {len(daily_avg)} days")

    daily_avg.to_csv("oregon_temp_daily_avg.csv", index=False)

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("oregon_temp_daily_avg.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file oregon_temp_daily_avg.csv must be created and uploaded to S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_temp_daily_avg.csv") or os.path.getsize("oregon_temp_daily_avg.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file oregon_temp_daily_avg.csv must not be empty")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_temp_raw.csv (tracked at require time)
    try:
        import pandas as _pd; _pd.read_csv("oregon_temp_daily_avg.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file oregon_temp_daily_avg.csv must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_exactly_two_columns_date_and_avg_temperature):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must have exactly two columns named 'date' and 'avg_temperature'")
        raise SystemExit(1)
    if not (date_column_contains_valid_dates):
        faasr_log("[PROMISE] CONTRACT VIOLATION: The 'date' column in the output CSV must contain valid date values")
        raise SystemExit(1)
    if not (avg_temperature_column_is_numeric):
        faasr_log("[PROMISE] CONTRACT VIOLATION: The 'avg_temperature' column in the output CSV must contain numeric (float) values")
        raise SystemExit(1)
    if not (dates_are_sorted_ascending):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Rows in the output CSV must be sorted in ascending order by date")
        raise SystemExit(1)
    if not (one_row_per_unique_date):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Each date in the output CSV must appear exactly once (one daily average per day)")
        raise SystemExit(1)
    if not (log_contains_uploaded_daily_average_temperatures):
        faasr_log("[PROMISE] CONTRACT VIOLATION: faasr_log must confirm successful upload of daily average temperatures to S3")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file="oregon_temp_daily_avg.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded daily average temperatures to S3")