def compute_daily_averages(folder: str, input1: str, output1: str) -> None:
    import os
    import pandas as pd

    faasr_get_file(local_file="raw_temperature.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    if not os.path.exists("raw_temperature.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Raw temperature input file must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("raw_temperature.csv") or os.path.getsize("raw_temperature.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Raw temperature input file must not be empty")
        raise SystemExit(1)
    try:
        import csv as _csv
        with open("raw_temperature.csv", newline="") as _f:
            next(_csv.reader(_f))
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Raw temperature input file must be a valid CSV: " + str(_e))
        raise SystemExit(1)
    # --- end requires ---


    faasr_log("Downloaded raw temperature data from S3")

    df = pd.read_csv("raw_temperature.csv")
    faasr_log(f"Loaded raw data with {len(df)} rows and columns: {list(df.columns)}")

    df["date"] = pd.to_datetime(df["date"])
    dec2025_df = df[(df["date"].dt.year == 2025) & (df["date"].dt.month == 12)].copy()
    faasr_log(f"Filtered to December 2025: {len(dec2025_df)} rows remaining")

    if len(dec2025_df) == 0:
        err_msg = "No records found for December 2025 in the raw temperature data"
        faasr_log(err_msg)
        raise RuntimeError(err_msg)

    # Prefer TAVG; fall back to mean of TMAX and TMIN; else first numeric column
    if "tavg" in dec2025_df.columns and dec2025_df["tavg"].notna().any():
        temp_col = "tavg"
    elif "tmax" in dec2025_df.columns and "tmin" in dec2025_df.columns:
        dec2025_df["tavg_computed"] = (dec2025_df["tmax"] + dec2025_df["tmin"]) / 2.0
        temp_col = "tavg_computed"
        faasr_log("TAVG not available; computing daily average as mean of TMAX and TMIN")
    else:
        numeric_cols = dec2025_df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            err_msg = "No numeric temperature columns available in the dataset"
            faasr_log(err_msg)
            raise ValueError(err_msg)
        temp_col = numeric_cols[0]
        faasr_log(f"Using fallback numeric column: {temp_col}")

    daily_avg = (
        dec2025_df.groupby("date")[temp_col]
        .mean()
        .reset_index()
        .rename(columns={temp_col: "avg_temperature"})
    )
    daily_avg["date"] = daily_avg["date"].dt.strftime("%Y-%m-%d")
    daily_avg = daily_avg.sort_values("date").reset_index(drop=True)

    faasr_log(f"Computed daily averages for {len(daily_avg)} days in December 2025")

    local_out = "daily_avg_temperature.csv"
    daily_avg.to_csv(local_out, index=False)


    # --- CONTRACT: promises ---
    if not os.path.exists("daily_avg_temperature.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Daily averages output file must exist after computation")
        raise SystemExit(1)
    if not os.path.exists("daily_avg_temperature.csv") or os.path.getsize("daily_avg_temperature.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Daily averages output file must not be empty")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: raw_temperature.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded daily average temperature CSV to S3")