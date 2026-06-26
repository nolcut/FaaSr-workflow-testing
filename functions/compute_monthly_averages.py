def compute_monthly_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    faasr_get_file(local_file="oregon_temperature_jan2026.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("oregon_temperature_jan2026.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must exist on S3 before processing")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_jan2026.csv") or os.path.getsize("oregon_temperature_jan2026.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_temperature_jan2026.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV file ({_e})")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded raw Oregon temperature CSV from S3")

    df = pd.read_csv("oregon_temperature_jan2026.csv")
    faasr_log(f"Loaded {len(df)} rows from input CSV")
    faasr_log(f"Columns found: {list(df.columns)}")

    # Identify the date column
    date_col = None
    for candidate in ["DATE", "Date", "date"]:
        if candidate in df.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError("No date column found in CSV")

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["year_month"] = df[date_col].dt.to_period("M").astype(str)

    # Determine temperature column and unit
    unit = "C"
    if "TAVG" in df.columns:
        temp_col = "TAVG"
        df[temp_col] = pd.to_numeric(df[temp_col], errors="coerce")
        faasr_log("Using TAVG column for temperature")
    elif "TMAX" in df.columns and "TMIN" in df.columns:
        df["TMAX"] = pd.to_numeric(df["TMAX"], errors="coerce")
        df["TMIN"] = pd.to_numeric(df["TMIN"], errors="coerce")
        df["TAVG_derived"] = (df["TMAX"] + df["TMIN"]) / 2.0
        temp_col = "TAVG_derived"
        faasr_log("Derived TAVG from TMAX and TMIN")
    else:
        # Try to find any temperature-like column
        temp_candidates = [c for c in df.columns if "TEMP" in c.upper() or "TAVG" in c.upper() or "TMAX" in c.upper()]
        if temp_candidates:
            temp_col = temp_candidates[0]
            df[temp_col] = pd.to_numeric(df[temp_col], errors="coerce")
            faasr_log(f"Using fallback temperature column: {temp_col}")
        else:
            raise ValueError("No recognizable temperature column found in CSV")

    df = df.dropna(subset=[temp_col])
    faasr_log(f"After dropping NaN temperatures: {len(df)} rows")

    monthly = (
        df.groupby("year_month")[temp_col]
        .mean()
        .reset_index()
        .rename(columns={temp_col: "avg_temperature", "year_month": "year_month"})
    )
    monthly["unit"] = unit
    monthly = monthly[["year_month", "avg_temperature", "unit"]]
    monthly["avg_temperature"] = monthly["avg_temperature"].round(2)

    faasr_log(f"Computed monthly averages for {len(monthly)} month(s)")
    faasr_log(f"Monthly averages:\n{monthly.to_string(index=False)}")

    monthly.to_csv("oregon_monthly_averages.csv", index=False)
    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_monthly_averages.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output monthly averages CSV must exist after processing")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_averages.csv") or os.path.getsize("oregon_monthly_averages.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output monthly averages CSV must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_monthly_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output monthly averages file must be a valid CSV file ({_e})")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_temperature_jan2026.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="oregon_monthly_averages.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded monthly averages CSV to S3")