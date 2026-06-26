def compute_monthly_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import numpy as np

    faasr_get_file(local_file="raw_data.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("raw_data.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_data.csv must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("raw_data.csv") or os.path.getsize("raw_data.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_data.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("raw_data.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file raw_data.csv must be a valid CSV file ({_e})")
        raise SystemExit(1)
    # FORMAT check for columns:date,tmax_f,tmin_f,tavg_f on raw_data.csv (not yet implemented)
    # --- end requires ---
    faasr_log(f"Downloaded raw temperature data from S3: {input1}")

    df = pd.read_csv("raw_data.csv")
    faasr_log(f"Loaded raw data with {len(df)} rows and columns: {list(df.columns)}")

    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')

    monthly_avg = df.groupby('month').agg(
        avg_tmax_f=('tmax_f', 'mean'),
        avg_tmin_f=('tmin_f', 'mean'),
        avg_tavg_f=('tavg_f', 'mean')
    ).reset_index()

    monthly_avg['month'] = monthly_avg['month'].astype(str)

    monthly_avg = monthly_avg.round({'avg_tmax_f': 2, 'avg_tmin_f': 2, 'avg_tavg_f': 2})

    faasr_log(f"Computed monthly averages for {len(monthly_avg)} month(s)")

    monthly_avg.to_csv("monthly_averages.csv", index=False)

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("monthly_averages.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file monthly_averages.csv must exist after processing")
        raise SystemExit(1)
    if not os.path.exists("monthly_averages.csv") or os.path.getsize("monthly_averages.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file monthly_averages.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("monthly_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file monthly_averages.csv must be a valid CSV file ({_e})")
        raise SystemExit(1)
    # FORMAT check for columns:month,avg_tmax_f,avg_tmin_f,avg_tavg_f on monthly_averages.csv (not yet implemented)
    # INPUTS_UNCHANGED: raw_data.csv (tracked at require time)
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: No error or Error messages should appear in faasr_log output during execution")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file="monthly_averages.csv", remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded monthly averages to S3: {output1}")