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
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'raw_temperature.csv' must be a valid CSV file parseable by pandas ({_e})")
        raise SystemExit(1)
    if not (column_count >= 2):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least 2 columns (one timestamp-like column and one numeric temperature-like column)")
        raise SystemExit(1)
    if not (has_parseable_datetime_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one column whose values are parseable as datetime by pandas")
        raise SystemExit(1)
    if not (has_numeric_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one numeric column to be used as the temperature reading")
        raise SystemExit(1)
    if not (row_count >= 1):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one data row (excluding header) to compute daily averages")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw temperature data from S3")

    df = pd.read_csv("raw_temperature.csv")
    faasr_log(f"Loaded raw temperature data with {len(df)} rows and columns: {list(df.columns)}")

    # Try to identify the timestamp column
    timestamp_col = None
    for col in df.columns:
        if col.lower() in ("timestamp", "datetime", "date", "time"):
            timestamp_col = col
            break
    if timestamp_col is None:
        timestamp_col = df.columns[0]
    faasr_log(f"Using '{timestamp_col}' as the timestamp column")

    # Try to identify the temperature column
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
        temp_col = df.columns[1]
    faasr_log(f"Using '{temp_col}' as the temperature column")

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
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'daily_averages.csv' must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_columns=['date', 'average_temperature']):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must have exactly the columns 'date' and 'average_temperature'")
        raise SystemExit(1)
    if not (column_average_temperature_is_numeric):
        faasr_log("[PROMISE] CONTRACT VIOLATION: The 'average_temperature' column in the output CSV must contain only numeric values")
        raise SystemExit(1)
    if not (column_date_is_sorted_ascending):
        faasr_log("[PROMISE] CONTRACT VIOLATION: The 'date' column in the output CSV must be sorted in ascending order")
        raise SystemExit(1)
    if not (column_date_has_unique_values):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Each date in the output CSV must appear exactly once (one row per unique day)")
        raise SystemExit(1)
    if not (row_count <= input_raw_temperature_csv_unique_date_count):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV row count must not exceed the number of unique dates present in the input CSV")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: raw_temperature.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded daily averages CSV to S3")