def plot_temperature_line_chart(folder: str, daily_averages: str, temperature_chart: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    faasr_get_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=daily_averages)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("daily_averages.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'daily_averages.csv' must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("daily_averages.csv") or os.path.getsize("daily_averages.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'daily_averages.csv' must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("daily_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'daily_averages.csv' must be a valid CSV file ({_e})")
        raise SystemExit(1)
    if not (has_at_least_2_columns):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least 2 columns (one for dates, one for temperature values)")
        raise SystemExit(1)
    if not (has_at_least_1_row):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one data row to produce a meaningful chart")
        raise SystemExit(1)
    if not (date_column_parseable):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The identified date column in 'daily_averages.csv' must contain values parseable by pd.to_datetime")
        raise SystemExit(1)
    if not (temperature_column_numeric):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The identified temperature column in 'daily_averages.csv' must contain numeric values suitable for plotting")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded daily averages CSV for plotting")

    df = pd.read_csv("daily_averages.csv")
    faasr_log(f"Loaded daily averages with {len(df)} rows and columns: {list(df.columns)}")

    # Try to identify date and temperature columns
    date_col = None
    temp_col = None

    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ["date", "day", "time"]):
            date_col = col
            break

    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ["temp", "avg", "average", "mean", "value"]):
            temp_col = col
            break

    if date_col is None:
        date_col = df.columns[0]
    if temp_col is None:
        temp_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    faasr_log(f"Using date column: '{date_col}', temperature column: '{temp_col}'")

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(by=date_col)

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(df[date_col], df[temp_col], color="steelblue", linewidth=2, marker="o", markersize=4, label="Daily Avg Temp")

    ax.set_title("Oregon Daily Average Temperatures — January 2026", fontsize=16, fontweight="bold")
    ax.set_xlabel("Date", fontsize=13)
    ax.set_ylabel("Temperature (°F)", fontsize=13)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45)

    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(fontsize=11)

    plt.tight_layout()
    plt.savefig("temperature_chart.png", dpi=150)
    plt.close()

    faasr_log("Line chart created and saved locally")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'temperature_chart.png' must exist locally after chart generation")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart.png") or os.path.getsize("temperature_chart.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'temperature_chart.png' must not be empty after chart generation")
        raise SystemExit(1)
    if not (valid_png_header):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file 'temperature_chart.png' must be a valid PNG image (correct magic bytes)")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: daily_averages.csv (tracked at require time)
    if not (log_contains_uploaded_confirmation):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must contain confirmation that the temperature line chart was uploaded to S3")
        raise SystemExit(1)
    if not (log_contains_identified_columns):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must record which date and temperature columns were identified for plotting")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file="temperature_chart.png", remote_folder=folder, remote_file=temperature_chart)
    faasr_log(f"Uploaded temperature line chart to S3 as '{temperature_chart}'")