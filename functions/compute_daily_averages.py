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
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least 2 columns (one for timestamps, one for temperature values)")
        raise SystemExit(1)
    if not (has_parseable_datetime_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one column parseable as datetime for grouping by date")
        raise SystemExit(1)
    if not (has_numeric_temperature_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one numeric column usable as temperature values")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw temperature data from S3")

    df = pd.read_csv("raw_temperature.csv")
    faasr_log(f"Loaded raw temperature data with {len(df)} rows and columns: {list(df.columns)}")

    # Try to identify the timestamp and temperature columns
    timestamp_col = None
    temperature_col = None

    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["time", "date", "timestamp", "datetime"]):
            timestamp_col = col
        if any(kw in col_lower for kw in ["temp", "temperature", "celsius", "fahrenheit", "value"]):
            temperature_col = col

    if timestamp_col is None:
        timestamp_col = df.columns[0]
        faasr_log(f"No timestamp column detected, using first column: {timestamp_col}")
    if temperature_col is None:
        # Use the last numeric column
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        temperature_col = numeric_cols[-1] if numeric_cols else df.columns[1]
        faasr_log(f"No temperature column detected, using: {temperature_col}")

    faasr_log(f"Using timestamp column: '{timestamp_col}', temperature column: '{temperature_col}'")

    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    df["date"] = df[timestamp_col].dt.date

    # Filter for January 2026
    df_jan2026 = df[(df[timestamp_col].dt.year == 2026) & (df[timestamp_col].dt.month == 1)]

    if df_jan2026.empty:
        faasr_log("Warning: No data found for January 2026, computing daily averages for all available data")
        df_filtered = df
    else:
        faasr_log(f"Filtered to {len(df_jan2026)} rows for January 2026")
        df_filtered = df_jan2026

    daily_avg = df_filtered.groupby("date")[temperature_col].mean().reset_index()
    daily_avg.columns = ["date", "average_temperature"]
    daily_avg["date"] = pd.to_datetime(daily_avg["date"])
    daily_avg = daily_avg.sort_values("date")

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
    # INPUTS_UNCHANGED: raw_temperature.csv (tracked at require time)
    try:
        import pandas as _pd; _pd.read_csv("daily_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file daily_averages.csv must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_columns_date_and_average_temperature):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain exactly the columns 'date' and 'average_temperature'")
        raise SystemExit(1)
    if not (date_column_is_sorted_ascending):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'date' column must be sorted in ascending order")
        raise SystemExit(1)
    if not (date_column_has_no_duplicates):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'date' column must contain unique dates (one row per day)")
        raise SystemExit(1)
    if not (average_temperature_column_is_numeric):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'average_temperature' column must contain only numeric (float) values")
        raise SystemExit(1)
    if not (row_count_less_than_or_equal_to_input_row_count):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must have fewer or equal rows compared to the input (aggregation reduces row count)")
        raise SystemExit(1)
    if not (log_contains_computed_daily_averages_message):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must contain a message confirming daily averages were computed for at least 1 day")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=daily_averages)
    faasr_log("Uploaded daily averages CSV to S3")