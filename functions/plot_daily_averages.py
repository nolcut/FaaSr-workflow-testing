def plot_daily_averages(folder: str, input2: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    faasr_get_file(local_file="daily_avg.csv", remote_folder=folder, remote_file=input2)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("daily_avg.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file daily_avg.csv must exist after download from S3 (oregon_daily_avg_temperature_jan2026.csv)")
        raise SystemExit(1)
    if not os.path.exists("daily_avg.csv") or os.path.getsize("daily_avg.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file daily_avg.csv must not be empty")
        raise SystemExit(1)
    # FORMAT check for has_columns:date,average_temperature on daily_avg.csv (not yet implemented)
    if not (column_parseable_as_datetime:date):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The 'date' column in daily_avg.csv must be parseable as datetime values")
        raise SystemExit(1)
    if not (column_numeric:average_temperature):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The 'average_temperature' column in daily_avg.csv must contain numeric values")
        raise SystemExit(1)
    if not (date_range_within:2026-01-01,2026-01-31):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The 'date' column values should fall within January 2026 (2026-01-01 to 2026-01-31) to match the plot's fixed x-axis range")
        raise SystemExit(1)
    if not (no_null_values:date,average_temperature):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Columns 'date' and 'average_temperature' must not contain null or NaN values")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded daily average temperature CSV from S3")

    df = pd.read_csv("daily_avg.csv")
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df['date'], df['average_temperature'], marker='o', linewidth=2, color='steelblue', markersize=4)

    ax.set_title('Daily Average Temperatures – January 2026', fontsize=16, fontweight='bold')
    ax.set_xlabel('Date', fontsize=13)
    ax.set_ylabel('Average Temperature (°C)', fontsize=13)

    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.xticks(rotation=45, ha='right')

    ax.set_xlim(pd.Timestamp('2026-01-01'), pd.Timestamp('2026-01-31'))
    ax.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.savefig("daily_avg_plot.png", dpi=150)
    plt.close()

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("daily_avg_plot.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file daily_avg_plot.png must exist after plot generation")
        raise SystemExit(1)
    if not os.path.exists("daily_avg_plot.png") or os.path.getsize("daily_avg_plot.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file oregon_daily_avg_temperature_jan2026.png uploaded to S3 must not be empty")
        raise SystemExit(1)
    # FORMAT check for valid_png_header on daily_avg_plot.png (not yet implemented)
    if not (min_file_size_bytes:10000):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG must be at least 10KB, indicating a non-trivial plot was rendered at dpi=150")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_daily_avg_temperature_jan2026.csv (tracked at require time)
    if not (contains_message:Downloaded daily average temperature CSV from S3):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must confirm successful download of the daily average temperature CSV from S3")
        raise SystemExit(1)
    if not (contains_message:Uploaded daily average temperature plot PNG to S3):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must confirm successful upload of the daily average temperature plot PNG to S3")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file="daily_avg_plot.png", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded daily average temperature plot PNG to S3")