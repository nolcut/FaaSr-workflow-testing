def compute_daily_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    faasr_get_file(local_file="raw_temperature.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("raw_temperature.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must exist locally after download from S3")
        raise SystemExit(1)
    if not os.path.exists("raw_temperature.csv") or os.path.getsize("raw_temperature.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("raw_temperature.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must be a valid CSV file parseable by pandas ({_e})")
        raise SystemExit(1)
    if not (has_at_least_one_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least one column to identify a timestamp or temperature field")
        raise SystemExit(1)
    if not (timestamp_column_parseable_as_datetime):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The identified or fallback timestamp column must be parseable as datetime by pandas")
        raise SystemExit(1)
    if not (temperature_column_is_numeric):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The identified or fallback temperature column must contain numeric values suitable for computing a mean")
        raise SystemExit(1)
    if not (has_at_least_one_non_null_row):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least one non-null row to produce a meaningful daily average")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw temperature data from S3")

    df = pd.read_csv("raw_temperature.csv")
    faasr_log(f"Loaded raw temperature data with {len(df)} rows and columns: {list(df.columns)}")

    # Identify timestamp and temperature columns
    timestamp_col = None
    temperature_col = None

    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ["time", "date", "timestamp"]):
            timestamp_col = col
        if any(keyword in col_lower for keyword in ["temp", "temperature"]):
            temperature_col = col

    if timestamp_col is None:
        timestamp_col = df.columns[0]
        faasr_log(f"No timestamp column found, using first column: {timestamp_col}")
    if temperature_col is None:
        temperature_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        faasr_log(f"No temperature column found, using column: {temperature_col}")

    faasr_log(f"Using timestamp column: '{timestamp_col}', temperature column: '{temperature_col}'")

    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    df["date"] = df[timestamp_col].dt.date

    daily_avg = df.groupby("date")[temperature_col].mean().reset_index()
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
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file daily_averages.csv must exist locally after processing")
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
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must have exactly the columns 'date' and 'average_temperature'")
        raise SystemExit(1)
    if not (date_column_is_sorted_ascending):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'date' column must be sorted in ascending order")
        raise SystemExit(1)
    if not (average_temperature_column_is_numeric):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'average_temperature' column must contain only numeric (float/int) values")
        raise SystemExit(1)
    if not (row_count_less_than_or_equal_to_input_row_count):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must have no more rows than distinct dates in the input (aggregation reduces or equals row count)")
        raise SystemExit(1)
    if not (date_column_contains_unique_dates):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Each row in the output CSV must correspond to a unique date (one row per day)")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: raw_temperature.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded daily averages to S3")