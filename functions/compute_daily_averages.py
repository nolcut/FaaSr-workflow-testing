def compute_daily_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    faasr_get_file(local_file="raw_temperature.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("raw_temperature.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'raw_temperature.csv' must exist locally after download from S3")
        raise SystemExit(1)
    if not os.path.exists("raw_temperature.csv") or os.path.getsize("raw_temperature.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'raw_temperature.csv' must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("raw_temperature.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'raw_temperature.csv' must be a valid, parseable CSV ({_e})")
        raise SystemExit(1)
    if not (at_least_two_columns):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least two columns (one for timestamps, one for temperature values)")
        raise SystemExit(1)
    if not (has_parseable_datetime_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one column parseable as datetime (named 'timestamp', 'datetime', 'date', 'time', or first column must be datetime-parseable)")
        raise SystemExit(1)
    if not (has_numeric_temperature_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one numeric column usable as temperature values (named 'temperature', 'temp', 'value', 'reading', or any non-timestamp numeric column)")
        raise SystemExit(1)
    if not (at_least_one_data_row):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one data row (excluding the header) to compute daily averages")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw temperature data from S3")

    df = pd.read_csv("raw_temperature.csv")
    faasr_log(f"Loaded raw temperature data with {len(df)} rows and columns: {list(df.columns)}")

    # Identify the timestamp column (try common names)
    timestamp_col = None
    for col in df.columns:
        if col.lower() in ("timestamp", "datetime", "date", "time"):
            timestamp_col = col
            break
    if timestamp_col is None:
        timestamp_col = df.columns[0]
        faasr_log(f"No obvious timestamp column found; using first column '{timestamp_col}' as timestamp")

    # Identify the temperature column (try common names)
    temp_col = None
    for col in df.columns:
        if col.lower() in ("temperature", "temp", "value", "reading"):
            temp_col = col
            break
    if temp_col is None:
        # Pick the first numeric column that is not the timestamp column
        for col in df.columns:
            if col != timestamp_col and pd.api.types.is_numeric_dtype(df[col]):
                temp_col = col
                break
    if temp_col is None:
        temp_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        faasr_log(f"No obvious temperature column found; using column '{temp_col}'")

    faasr_log(f"Using timestamp column '{timestamp_col}' and temperature column '{temp_col}'")

    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    df["date"] = df[timestamp_col].dt.date

    daily_avg = df.groupby("date")[temp_col].mean().reset_index()
    daily_avg.columns = ["date", "average_temperature"]
    daily_avg = daily_avg.sort_values("date")

    faasr_log(f"Computed daily averages for {len(daily_avg)} days")

    daily_avg.to_csv("daily_averages.csv", index=False)

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("daily_averages.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'daily_averages.csv' must exist locally after processing")
        raise SystemExit(1)
    if not os.path.exists("daily_averages.csv") or os.path.getsize("daily_averages.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'daily_averages.csv' must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("daily_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'daily_averages.csv' must be a valid, parseable CSV ({_e})")
        raise SystemExit(1)
    if not (has_exactly_two_columns:date,average_temperature):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must have exactly two columns named 'date' and 'average_temperature'")
        raise SystemExit(1)
    if not (date_column_sorted_ascending):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'date' column must be sorted in ascending chronological order")
        raise SystemExit(1)
    if not (average_temperature_column_is_numeric):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'average_temperature' column must contain only numeric (float/int) values")
        raise SystemExit(1)
    if not (row_count_less_than_or_equal_to_input_row_count):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV row count must not exceed the number of data rows in the input (aggregation cannot produce more rows than unique dates)")
        raise SystemExit(1)
    if not (no_duplicate_dates):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must not contain duplicate dates — each date must appear exactly once as a grouped daily average")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: raw_temperature.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded daily averages CSV to S3")