def plot_daily_temperatures(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt

    faasr_get_file(local_file="oregon_temp_daily_avg.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("oregon_temp_daily_avg.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file oregon_temp_daily_avg.csv must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_temp_daily_avg.csv") or os.path.getsize("oregon_temp_daily_avg.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV oregon_temp_daily_avg.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_temp_daily_avg.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV parseable by pandas ({_e})")
        raise SystemExit(1)
    if not (has_at_least_one_column):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least one column to identify a date or temperature field")
        raise SystemExit(1)
    if not (has_at_least_two_columns):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV should have at least two columns so separate date and temperature columns can be resolved")
        raise SystemExit(1)
    if not (date_column_parseable_as_datetime):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The resolved date column values must be parseable by pandas.to_datetime without errors")
        raise SystemExit(1)
    if not (temperature_column_is_numeric):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: The resolved temperature column must contain numeric values suitable for plotting")
        raise SystemExit(1)
    if not (has_at_least_one_data_row):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one data row (beyond the header) to produce a meaningful plot")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded daily average temperature CSV from S3")

    df = pd.read_csv("oregon_temp_daily_avg.csv")
    faasr_log(f"Loaded CSV with {len(df)} rows and columns: {list(df.columns)}")

    date_col = None
    temp_col = None

    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ["date", "day", "time"]):
            date_col = col
        if any(keyword in col_lower for keyword in ["temp", "avg", "average", "mean"]):
            temp_col = col

    if date_col is None:
        date_col = df.columns[0]
    if temp_col is None:
        temp_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    faasr_log(f"Using date column: '{date_col}', temperature column: '{temp_col}'")

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(by=date_col)

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(df[date_col], df[temp_col], marker="o", linewidth=2, color="steelblue", markersize=5, label="Daily Avg Temp")

    ax.set_title("Oregon Daily Average Temperatures — January 2026", fontsize=16, fontweight="bold")
    ax.set_xlabel("Date", fontsize=13)
    ax.set_ylabel("Temperature (°F)" if "f" in temp_col.lower() else "Temperature", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.6)

    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    plt.savefig("oregon_temp_jan2026_plot.png", dpi=150)
    plt.close()
    faasr_log("Line plot saved locally as oregon_temp_jan2026_plot.png")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("oregon_temp_jan2026_plot.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output plot file oregon_temp_jan2026_plot.png must exist after saving")
        raise SystemExit(1)
    if not os.path.exists("oregon_temp_jan2026_plot.png") or os.path.getsize("oregon_temp_jan2026_plot.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output plot file oregon_temp_jan2026_plot.png must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on oregon_temp_jan2026_plot.png (not yet implemented)
    # INPUTS_UNCHANGED: oregon_temp_daily_avg.csv (tracked at require time)
    if not (log_contains_downloaded_confirmation):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must confirm that the CSV was successfully downloaded from S3")
        raise SystemExit(1)
    if not (log_contains_uploaded_confirmation):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must confirm that the PNG plot was successfully uploaded to S3")
        raise SystemExit(1)
    if not (image_dimensions_at_least_100x100):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG must represent a real plot with meaningful pixel dimensions (at least 100x100)")
        raise SystemExit(1)
    if not (log_contains_date_and_temp_column_names):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must record which date and temperature columns were resolved for traceability")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file="oregon_temp_jan2026_plot.png", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded line plot PNG to S3")