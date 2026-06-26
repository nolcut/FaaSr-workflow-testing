def compute_monthly_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    faasr_get_file(local_file="raw_temperature.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("raw_temperature.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must be downloaded from S3 before processing")
        raise SystemExit(1)
    if not os.path.exists("raw_temperature.csv") or os.path.getsize("raw_temperature.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("raw_temperature.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_temperature.csv must be a valid CSV with 'date' and 'temperature' columns ({_e})")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log(f"Downloaded {input1} from folder {folder}")

    df = pd.read_csv("raw_temperature.csv")

    required_cols = {"date", "temperature"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required column(s): {sorted(missing)}. "
            f"Found columns: {list(df.columns)}"
        )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    invalid_dates = int(df["date"].isna().sum())
    if invalid_dates > 0:
        faasr_log(f"Warning: {invalid_dates} rows had unparseable dates and were dropped")
    df = df.dropna(subset=["date"])

    df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")

    df["month"] = df["date"].dt.strftime("%Y-%m")

    monthly = (
        df.groupby("month")["temperature"]
        .mean()
        .reset_index()
        .rename(columns={"temperature": "avg_temperature"})
    )
    monthly = monthly.sort_values("month").reset_index(drop=True)

    monthly.to_csv("monthly_averages.csv", index=False)
    # --- CONTRACT: promises ---
    if not os.path.exists("monthly_averages.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file monthly_averages.csv must be created after computing monthly averages")
        raise SystemExit(1)
    if not os.path.exists("monthly_averages.csv") or os.path.getsize("monthly_averages.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file monthly_averages.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("monthly_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file monthly_averages.csv must be a valid CSV ({_e})")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: raw_temperature.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="monthly_averages.csv", remote_folder=folder, remote_file=output1)
    faasr_log(f"Computed monthly averages for {len(monthly)} month(s); wrote {output1}")