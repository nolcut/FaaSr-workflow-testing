def compute_monthly_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import numpy as np

    faasr_get_file(local_file="oregon_temperature_jan2026.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("oregon_temperature_jan2026.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must exist before processing")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_jan2026.csv") or os.path.getsize("oregon_temperature_jan2026.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_temperature_jan2026.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV format with at least one column ({_e})")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw Oregon temperature CSV from S3")

    try:
        df = pd.read_csv("oregon_temperature_jan2026.csv")
    except Exception as e:
        faasr_log(f"Error reading CSV file: {e}")
        raise

    faasr_log(f"Loaded {len(df)} rows from input CSV")
    faasr_log(f"Columns found: {list(df.columns)}")

    # Try to identify date and temperature columns flexibly
    date_col = None
    temp_col = None

    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ['date', 'time', 'day', 'month', 'year']):
            if date_col is None:
                date_col = col
        if any(kw in col_lower for kw in ['temp', 'temperature', 'tmax', 'tmin', 'tavg', 'tmean', 'value']):
            if temp_col is None:
                temp_col = col

    # Fallback: use first column as date, second as temperature
    if date_col is None:
        date_col = df.columns[0]
        faasr_log(f"No date column detected by name, using first column: '{date_col}'")
    if temp_col is None:
        temp_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        faasr_log(f"No temperature column detected by name, using column: '{temp_col}'")

    faasr_log(f"Using date column: '{date_col}', temperature column: '{temp_col}'")

    # Parse dates with error coercion to handle malformed records
    df['parsed_date'] = pd.to_datetime(df[date_col], errors='coerce')

    # Convert temperature to numeric, coercing errors
    df['parsed_temp'] = pd.to_numeric(df[temp_col], errors='coerce')

    # Report and drop malformed records
    bad_dates = df['parsed_date'].isna().sum()
    bad_temps = df['parsed_temp'].isna().sum()
    if bad_dates > 0:
        faasr_log(f"Dropping {bad_dates} rows with unparseable dates")
    if bad_temps > 0:
        faasr_log(f"Dropping {bad_temps} rows with unparseable temperature values")

    df_clean = df.dropna(subset=['parsed_date', 'parsed_temp']).copy()
    faasr_log(f"{len(df_clean)} valid records remaining after cleaning")

    if df_clean.empty:
        faasr_log("WARNING: No valid records found after cleaning; writing empty output file")
        result = pd.DataFrame(columns=['year_month', 'avg_temperature'])
        result.to_csv("oregon_monthly_averages.csv", index=False)
    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_monthly_averages.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output monthly averages CSV must exist after processing")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_averages.csv") or os.path.getsize("oregon_monthly_averages.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output monthly averages CSV must not be empty (must contain at least a header row)")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_monthly_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file must be a valid CSV with columns: year_month, avg_temperature ({_e})")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_temperature_jan2026.csv (tracked at require time)
    # --- end promises ---
        faasr_put_file(local_file="oregon_monthly_averages.csv", remote_folder=folder, remote_file=output1)
        faasr_log("Uploaded empty monthly averages CSV to S3")
        return

    # Create year_month grouping key
    df_clean['year_month'] = df_clean['parsed_date'].dt.to_period('M').astype(str)

    # Compute mean temperature per year-month
    monthly_avg = (
        df_clean.groupby('year_month', sort=True)['parsed_temp']
        .mean()
        .reset_index()
        .rename(columns={'parsed_temp': 'avg_temperature'})
    )

    monthly_avg['avg_temperature'] = monthly_avg['avg_temperature'].round(4)

    faasr_log(f"Computed monthly averages for {len(monthly_avg)} month(s):")
    for _, row in monthly_avg.iterrows():
        faasr_log(f"  {row['year_month']}: {row['avg_temperature']}")

    monthly_avg.to_csv("oregon_monthly_averages.csv", index=False)
    faasr_put_file(local_file="oregon_monthly_averages.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded monthly averages CSV to S3")