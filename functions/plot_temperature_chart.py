def plot_temperature_chart(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt

    faasr_get_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("daily_averages.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file daily_averages.csv must be downloadable from S3 before processing")
        raise SystemExit(1)
    if not os.path.exists("daily_averages.csv") or os.path.getsize("daily_averages.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: daily_averages.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("daily_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: daily_averages.csv must be a valid CSV file parseable by pandas ({_e})")
        raise SystemExit(1)
    if not (has_index_column_parseable_as_dates):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: daily_averages.csv must have a first column parseable as datetime (used as DatetimeIndex)")
        raise SystemExit(1)
    if not (has_at_least_one_numeric_data_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: daily_averages.csv must contain at least one numeric data column beyond the date index for plotting")
        raise SystemExit(1)
    if not (row_count_gt_0):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: daily_averages.csv must contain at least one data row to produce a meaningful chart")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded daily_averages.csv from S3")

    df = pd.read_csv("daily_averages.csv", index_col=0, parse_dates=True)
    faasr_log(f"Loaded daily averages with {len(df)} rows")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df.index, df.iloc[:, 0], linewidth=1.5, color="steelblue", marker="o", markersize=3)
    ax.set_title("Daily Average Temperatures Over Time", fontsize=16)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Temperature", fontsize=12)
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig("temperature_chart.png", dpi=150)
    plt.close(fig)
    faasr_log("Generated temperature line chart")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: temperature_chart.png must exist locally after matplotlib savefig call")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart.png") or os.path.getsize("temperature_chart.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Uploaded temperature_chart.png must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on temperature_chart.png (not yet implemented)
    if not (image_dimensions_width_gte_1200_height_gte_600):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Generated PNG must reflect the 12x6 inch figure size at 150 dpi (approx 1800x900 pixels)")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: daily_averages.csv (tracked at require time)
    if not (log_contains_row_count_gt_0):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must confirm that at least one row was loaded from daily_averages.csv")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file="temperature_chart.png", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded temperature_chart.png to S3")