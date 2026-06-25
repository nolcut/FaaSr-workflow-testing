def plot_temperature_chart(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    faasr_get_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("daily_averages.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file daily_averages.csv must be downloadable from S3 before processing")
        raise SystemExit(1)
    if not os.path.exists("daily_averages.csv") or os.path.getsize("daily_averages.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file daily_averages.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("daily_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file daily_averages.csv must be a valid CSV file parseable by pandas ({_e})")
        raise SystemExit(1)
    if not (min_columns_2):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least 2 columns (one for dates, one for temperature values)")
        raise SystemExit(1)
    if not (min_rows_1):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least 1 data row to produce a meaningful chart")
        raise SystemExit(1)
    if not (date_column_parseable):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The detected date/time column in daily_averages.csv must be parseable by pandas to_datetime")
        raise SystemExit(1)
    if not (temperature_column_numeric):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The detected temperature/average column in daily_averages.csv must contain numeric values suitable for plotting")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log(f"Downloaded daily averages file: {input1}")

    df = pd.read_csv("daily_averages.csv")
    faasr_log(f"Loaded daily averages with {len(df)} rows and columns: {list(df.columns)}")

    date_col = None
    temp_col = None

    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ["date", "day", "time", "timestamp"]):
            date_col = col
            break

    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ["temp", "average", "avg", "mean", "value"]):
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

    ax.plot(df[date_col], df[temp_col], color="steelblue", linewidth=1.8, marker="o", markersize=3, label="Daily Avg Temperature")

    ax.set_title("Daily Average Temperatures Over Time", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Temperature", fontsize=12)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=45)

    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(fontsize=10)

    plt.tight_layout()
    plt.savefig("temperature_chart.png", dpi=150, bbox_inches="tight")
    plt.close()

    faasr_log("Temperature line chart saved as temperature_chart.png")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file temperature_chart.png must exist locally after matplotlib savefig")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart.png") or os.path.getsize("temperature_chart.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file temperature_chart.png must not be empty after generation")
        raise SystemExit(1)
    # FORMAT check for png on temperature_chart.png (not yet implemented)
    # INPUTS_UNCHANGED: daily_averages.csv (tracked at require time)
    if not (log_contains_date_col_and_temp_col):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must confirm which date column and temperature column were selected for plotting")
        raise SystemExit(1)
    if not (log_confirms_upload):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must confirm successful upload of temperature_chart.png to S3")
        raise SystemExit(1)
    if not (image_dimensions_min_800x400):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG chart must have sufficient dimensions (at least 800x400 pixels) reflecting the 12x6 inch / 150 dpi figure size")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file="temperature_chart.png", remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded temperature chart to S3 as: {output1}")