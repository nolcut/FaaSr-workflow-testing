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
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'oregon_temperature_january_2026.csv' must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_date_column: at least one of ['date','datetime','day','time'] must exist as a column (case-insensitive, whitespace-stripped)):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain a recognizable date column (e.g. 'date', 'datetime', 'day', or 'time')")
        raise SystemExit(1)
    if not (has_temperature_column: at least one of ['temperature_f','temperature','temp_f','temp','tmax','tmin','tavg','value'] must exist as a column (case-insensitive, whitespace-stripped)):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain a recognizable temperature column (e.g. 'temperature_f', 'temp', 'tavg', 'value', etc.)")
        raise SystemExit(1)
    if not (has_at_least_one_valid_temperature_row: at least one row must have a non-null, numeric temperature value after coercion):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one row with a valid numeric temperature value")
        raise SystemExit(1)
    if not (has_parseable_dates: at least one row must have a date column value parseable by pd.to_datetime):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one row with a parseable date value in the date column")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw daily temperature CSV from S3")

    df = pd.read_csv("oregon_temperature_january_2026.csv")
    faasr_log(f"Loaded {len(df)} rows from input CSV, columns: {list(df.columns)}")

    # Normalize column names to lowercase and strip whitespace
    df.columns = [col.strip().lower() for col in df.columns]

    # Resolve date column (support common variants)
    date_col = None
    for candidate in ["date", "datetime", "day", "time"]:
        if candidate in df.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError(f"No date column found. Available columns: {list(df.columns)}")

    # Resolve temperature column (support common variants)
    temp_col = None
    for candidate in ["temperature_f", "temperature", "temp_f", "temp", "tmax", "tmin", "tavg", "value"]:
        if candidate in df.columns:
            temp_col = candidate
            break
    if temp_col is None:
        raise ValueError(f"No temperature column found. Available columns: {list(df.columns)}")

    faasr_log(f"Using date column '{date_col}' and temperature column '{temp_col}'")

    # Parse dates and extract year-month
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df["month"] = df[date_col].dt.to_period("M").astype(str)

    # Drop null temperature values before computing mean
    df = df.dropna(subset=[temp_col])
    df[temp_col] = pd.to_numeric(df[temp_col], errors="coerce")
    df = df.dropna(subset=[temp_col])

    # Group by year-month and compute mean temperature
    monthly_avg = (
        df.groupby("month")[temp_col]
        .mean()
        .reset_index()
        .rename(columns={temp_col: "average_temperature"})
        .sort_values("month")
    )

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
    try:
        import pandas as _pd; _pd.read_csv("oregon_monthly_avg_temperature.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'oregon_monthly_avg_temperature.csv' must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_columns: output CSV must contain exactly columns ['month', 'average_temperature']):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must have exactly two columns: 'month' and 'average_temperature'")
        raise SystemExit(1)
    if not (month_format: all values in 'month' column must match YYYY-MM period string format):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'month' column values must follow YYYY-MM period format (e.g. '2026-01')")
        raise SystemExit(1)
    if not (average_temperature_numeric: all values in 'average_temperature' column must be numeric (float or int)):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV 'average_temperature' column must contain only numeric values")
        raise SystemExit(1)
    if not (month_sorted_ascending: rows in output CSV must be sorted in ascending order by 'month'):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV rows must be sorted in ascending order by the 'month' column")
        raise SystemExit(1)
    if not (no_null_values: output CSV must contain no null or missing values in either column):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must not contain any null or missing values in 'month' or 'average_temperature' columns")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_temperature_january_2026.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="oregon_monthly_avg_temperature.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded monthly average temperature CSV to S3")