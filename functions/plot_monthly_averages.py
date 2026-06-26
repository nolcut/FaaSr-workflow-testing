def plot_monthly_averages(folder: str, input2: str, output1: str) -> None:
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    local_input = "oregon_monthly_avg_temperature.csv"
    local_output = "oregon_monthly_avg_temperature_plot.png"

    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input2)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("oregon_monthly_avg_temperature.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file oregon_monthly_avg_temperature.csv must exist locally after download from S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperature.csv") or os.path.getsize("oregon_monthly_avg_temperature.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV oregon_monthly_avg_temperature.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_monthly_avg_temperature.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV parseable by pandas ({_e})")
        raise SystemExit(1)
    if not (has_column:month):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain a 'month' column for the x-axis of the plot")
        raise SystemExit(1)
    if not (has_column:average_temperature):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain an 'average_temperature' column for the y-axis of the plot")
        raise SystemExit(1)
    if not (row_count_gte:1):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least one data row to produce a meaningful plot")
        raise SystemExit(1)
    if not (column_numeric:average_temperature):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Column 'average_temperature' must contain numeric values suitable for plotting")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log(f"Downloaded {input2} from S3 folder {folder}")

    df = pd.read_csv(local_input)
    faasr_log(f"Loaded CSV with {len(df)} rows and columns: {list(df.columns)}")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df['month'], df['average_temperature'], marker='o', linewidth=2, markersize=5, color='steelblue')
    ax.set_xlabel('Month (YYYY-MM)', fontsize=12)
    ax.set_ylabel('Average Temperature (°F)', fontsize=12)
    ax.set_title('Oregon Monthly Average Temperature - January 2026', fontsize=14)
    ax.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    fig.savefig(local_output, dpi=150)
    plt.close(fig)
    faasr_log(f"Saved plot to {local_output}")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperature_plot.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output plot file oregon_monthly_avg_temperature_plot.png must exist after rendering")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperature_plot.png") or os.path.getsize("oregon_monthly_avg_temperature_plot.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output plot file oregon_monthly_avg_temperature_plot.png must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on oregon_monthly_avg_temperature_plot.png (not yet implemented)
    if not (file_size_gte_bytes:1024):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG must be at least 1KB, indicating a non-trivial image was rendered")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_monthly_avg_temperature.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded plot as {output1} to S3 folder {folder}")