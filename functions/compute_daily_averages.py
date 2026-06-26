def compute_daily_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    faasr_get_file(local_file="raw_temperature.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("raw_temperature.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Downloaded raw temperature file 'raw_temperature.csv' must exist before processing")
        raise SystemExit(1)
    if not os.path.exists("raw_temperature.csv") or os.path.getsize("raw_temperature.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Downloaded raw temperature file 'raw_temperature.csv' must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("raw_temperature.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'raw_temperature.csv' must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_columns:date,temperature):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain both 'date' and 'temperature' columns")
        raise SystemExit(1)
    if not (column_parseable_as_datetime:date):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The 'date' column in the input CSV must be parseable as datetime values")
        raise SystemExit(1)
    if not (column_numeric:temperature):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The 'temperature' column in the input CSV must contain numeric values")
        raise SystemExit(1)
    if not (has_rows_in_date_range:date,2026-01-01,2026-01-31):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input data must contain at least one row with a 'date' in January 2026")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw Oregon temperature data from S3")

    df = pd.read_csv("raw_temperature.csv")
    faasr_log(f"Loaded {len(df)} rows from raw temperature data")

    df['date'] = pd.to_datetime(df['date'])

    start_date = pd.Timestamp("2026-01-01")
    end_date = pd.Timestamp("2026-01-31")
    df_jan = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    faasr_log(f"Filtered to January 2026: {len(df_jan)} rows")

    daily_avg = df_jan.groupby('date')['temperature'].mean().reset_index()
    daily_avg.columns = ['date', 'average_temperature']
    daily_avg = daily_avg.sort_values('date').reset_index(drop=True)
    daily_avg['date'] = daily_avg['date'].dt.strftime('%Y-%m-%d')

    daily_avg.to_csv("daily_avg_temperature.csv", index=False)
    faasr_log(f"Computed daily averages for {len(daily_avg)} days")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("daily_avg_temperature.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'daily_avg_temperature.csv' must exist after processing")
        raise SystemExit(1)
    if not os.path.exists("daily_avg_temperature.csv") or os.path.getsize("daily_avg_temperature.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'daily_avg_temperature.csv' must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("daily_avg_temperature.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'daily_avg_temperature.csv' must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_columns:date,average_temperature):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain exactly 'date' and 'average_temperature' columns")
        raise SystemExit(1)
    if not (column_date_format:date,%Y-%m-%d):
        faasr_log("[PROMISE] CONTRACT VIOLATION: The 'date' column in the output CSV must follow the format 'YYYY-MM-DD'")
        raise SystemExit(1)
    if not (column_numeric:average_temperature):
        faasr_log("[PROMISE] CONTRACT VIOLATION: The 'average_temperature' column in the output CSV must contain numeric values")
        raise SystemExit(1)
    if not (dates_within_range:date,2026-01-01,2026-01-31):
        faasr_log("[PROMISE] CONTRACT VIOLATION: All dates in the output CSV must fall within January 2026")
        raise SystemExit(1)
    if not (dates_sorted_ascending:date):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV rows must be sorted in ascending order by 'date'")
        raise SystemExit(1)
    if not (max_row_count:31):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain at most 31 rows (one per day of January 2026)")
        raise SystemExit(1)
    if not (no_duplicate_values:date):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Each date in the output CSV must be unique (one row per day)")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_raw_temperature_jan2026.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="daily_avg_temperature.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded daily average temperature data to S3")