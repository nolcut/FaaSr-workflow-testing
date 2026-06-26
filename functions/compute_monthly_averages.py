def compute_monthly_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import numpy as np

    faasr_get_file(local_file="raw_temperatures.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("raw_temperatures.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'raw_temperatures.csv' (from S3: oregon_temperature_jan2026_raw.csv) must exist after download")
        raise SystemExit(1)
    if not os.path.exists("raw_temperatures.csv") or os.path.getsize("raw_temperatures.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'raw_temperatures.csv' must not be empty")
        raise SystemExit(1)
    # FORMAT check for csv_has_columns:date,temperature_c on raw_temperatures.csv (not yet implemented)
    # CUSTOM check skipped (non-Python predicate): 'column_parseable_as_datetime:date' — Column 'date' in input CSV must be parseable as datetime values
    # CUSTOM check skipped (non-Python predicate): 'column_is_numeric:temperature_c' — Column 'temperature_c' in input CSV must contain numeric values
    # CUSTOM check skipped (non-Python predicate): 'column_has_no_all_null:temperature_c' — Column 'temperature_c' must not be entirely null/NaN so that averages can be computed
    # --- end requires ---
    faasr_log(f"Downloaded raw temperature data from S3: {input1}")

    df = pd.read_csv("raw_temperatures.csv")
    faasr_log(f"Loaded {len(df)} records from raw temperature CSV")

    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    monthly_avg = (
        df.groupby(["year", "month"])["temperature_c"]
        .mean()
        .reset_index()
        .rename(columns={"temperature_c": "avg_temperature_c"})
    )

    monthly_avg["year"] = monthly_avg["year"].astype(int)
    monthly_avg["month"] = monthly_avg["month"].astype(int)
    monthly_avg["avg_temperature_c"] = monthly_avg["avg_temperature_c"].round(4)

    monthly_avg = monthly_avg.sort_values(["year", "month"]).reset_index(drop=True)

    monthly_avg.to_csv("monthly_avg.csv", index=False)
    faasr_log(f"Computed monthly averages for {len(monthly_avg)} month(s)")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("monthly_avg.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'monthly_avg.csv' must exist after processing")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_monthly_avg.csv") or os.path.getsize("oregon_temperature_monthly_avg.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output S3 file 'oregon_temperature_monthly_avg.csv' must not be empty")
        raise SystemExit(1)
    # FORMAT check for csv_has_columns:year,month,avg_temperature_c on monthly_avg.csv (not yet implemented)
    # CUSTOM check skipped (non-Python predicate): 'column_values_in_range:month:1:12' — Column 'month' in output CSV must contain values between 1 and 12 inclusive
    # CUSTOM check skipped (non-Python predicate): 'column_is_integer:year' — Column 'year' in output CSV must contain integer values
    # CUSTOM check skipped (non-Python predicate): 'column_is_integer:month' — Column 'month' in output CSV must contain integer values
    # CUSTOM check skipped (non-Python predicate): 'column_is_numeric:avg_temperature_c' — Column 'avg_temperature_c' in output CSV must contain numeric (float) values
    # CUSTOM check skipped (non-Python predicate): 'column_decimal_precision_max:avg_temperature_c:4' — Column 'avg_temperature_c' values must be rounded to at most 4 decimal places
    # CUSTOM check skipped (non-Python predicate): 'rows_sorted_ascending:year,month' — Output CSV rows must be sorted in ascending order by 'year' then 'month'
    # CUSTOM check skipped (non-Python predicate): 'no_duplicate_rows:year,month' — Output CSV must not contain duplicate (year, month) pairs
    # INPUTS_UNCHANGED: oregon_temperature_jan2026_raw.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="monthly_avg.csv", remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded monthly averages to S3: {output1}")