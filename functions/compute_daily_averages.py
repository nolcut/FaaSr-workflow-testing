def compute_daily_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    faasr_get_file(local_file="raw_temperature.csv", remote_folder=folder, remote_file=input1)
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
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must be a valid CSV file parseable by pandas ({_e})")
        raise SystemExit(1)
    if not (has_at_least_two_columns):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least two columns (one for timestamps and one for temperature values)")
        raise SystemExit(1)
    if not (timestamp_column_parseable_as_datetime):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The identified or fallback timestamp column must be parseable as datetime by pandas")
        raise SystemExit(1)
    if not (temperature_column_is_numeric_or_castable):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The identified or fallback temperature column must contain numeric (or castable to numeric) values to compute averages")
        raise SystemExit(1)
    if not (at_least_one_non_null_temperature_row):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The temperature column must have at least one non-null value to compute a meaningful daily average")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw temperature CSV from S3")

    df = pd.read_csv("raw_temperature.csv")
    faasr_log(f"Loaded raw temperature data with {len(df)} rows and columns: {list(df.columns)}")

    # Try to identify the timestamp/date column and temperature column
    timestamp_col = None
    temp_col = None

    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["time", "date", "timestamp", "datetime"]):
            timestamp_col = col
            break

    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["temp", "temperature", "value"]):
            temp_col = col
            break

    # Fallback: use first column as timestamp and second as temperature
    if timestamp_col is None:
        timestamp_col = df.columns[0]
        faasr_log(f"No timestamp column found by name; using first column: '{timestamp_col}'")
    if temp_col is None:
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            temp_col = numeric_cols[0]
        else:
            temp_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        faasr_log(f"No temperature column found by name; using column: '{temp_col}'")

    faasr_log(f"Using timestamp column: '{timestamp_col}', temperature column: '{temp_col}'")

    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    df["date"] = df[timestamp_col].dt.date

    daily_avg = df.groupby("date")[temp_col].mean().reset_index()
    daily_avg.columns = ["date", "average_temperature"]
    daily_avg["date"] = pd.to_datetime(daily_avg["date"])
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
    if not (has_columns_date_and_average_temperature):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain exactly the columns 'date' and 'average_temperature'")
        raise SystemExit(1)
    if not (date_column_is_sorted_ascending):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'date' column must be sorted in ascending chronological order")
        raise SystemExit(1)
    if not (no_duplicate_dates):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must have exactly one row per unique date (no duplicate dates)")
        raise SystemExit(1)
    if not (average_temperature_column_is_numeric):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'average_temperature' column must contain only numeric (float/int) values")
        raise SystemExit(1)
    if not (row_count_leq_input_row_count):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV row count must be less than or equal to the number of rows in the input (daily aggregation cannot produce more rows than input)")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: raw_temperature.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded daily_averages.csv to S3")