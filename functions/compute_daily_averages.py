def compute_daily_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import numpy as np

    faasr_get_file(local_file="oregon_temperature_jan2026.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("oregon_temperature_jan2026.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file oregon_temperature_jan2026.csv must exist before processing")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_jan2026.csv") or os.path.getsize("oregon_temperature_jan2026.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file oregon_temperature_jan2026.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_temperature_jan2026.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file oregon_temperature_jan2026.csv must be a valid CSV file: " + str(_e))
        raise SystemExit(1)
    # FORMAT check for has_column:date on oregon_temperature_jan2026.csv (not yet implemented)
    # FORMAT check for has_column:temperature_c on oregon_temperature_jan2026.csv (not yet implemented)
    # --- end requires ---
    faasr_log("Downloaded raw Oregon temperature data for January 2026")

    df = pd.read_csv("oregon_temperature_jan2026.csv")
    faasr_log(f"Loaded {len(df)} temperature readings")

    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

    daily_avg = df.groupby('date', as_index=False)['temperature_c'].mean()
    daily_avg.rename(columns={'temperature_c': 'avg_temperature_c'}, inplace=True)
    daily_avg = daily_avg.sort_values('date').reset_index(drop=True)

    faasr_log(f"Computed daily averages for {len(daily_avg)} days in January 2026")

    daily_avg.to_csv("daily_avg_temperature_jan2026.csv", index=False)

    # --- CONTRACT: promises ---
    if not os.path.exists("daily_avg_temperature_jan2026.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file daily_avg_temperature_jan2026.csv must exist after processing")
        raise SystemExit(1)
    if not os.path.exists("daily_avg_temperature_jan2026.csv") or os.path.getsize("daily_avg_temperature_jan2026.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file daily_avg_temperature_jan2026.csv must not be empty")
        raise SystemExit(1)
    # FORMAT check for has_column:date on daily_avg_temperature_jan2026.csv (not yet implemented)
    # FORMAT check for has_column:avg_temperature_c on daily_avg_temperature_jan2026.csv (not yet implemented)
    # INPUTS_UNCHANGED: oregon_temperature_jan2026.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="daily_avg_temperature_jan2026.csv", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded daily average temperature file to S3")