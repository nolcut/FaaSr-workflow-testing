def plot_monthly_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt

    faasr_get_file(local_file="oregon_monthly_avg_temperature.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("oregon_monthly_avg_temperature.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file oregon_monthly_avg_temperature.csv must exist locally after download from S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperature.csv") or os.path.getsize("oregon_monthly_avg_temperature.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV oregon_monthly_avg_temperature.csv must not be empty")
        raise SystemExit(1)
    # FORMAT check for csv_has_columns:month,average_temperature on oregon_monthly_avg_temperature.csv (not yet implemented)
    if not (row_count >= 1):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must have at least one data row to plot")
        raise SystemExit(1)
    if not (column_numeric:average_temperature):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Column 'average_temperature' must contain numeric values suitable for plotting")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded monthly average temperature CSV from S3")

    df = pd.read_csv("oregon_monthly_avg_temperature.csv")
    faasr_log(f"Loaded data with {len(df)} rows")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["month"], df["average_temperature"], marker="o", linewidth=2, color="steelblue")
    ax.set_title("Oregon Monthly Average Temperature (January 2026)", fontsize=14)
    ax.set_xlabel("Month (YYYY-MM)", fontsize=12)
    ax.set_ylabel("Average Temperature", fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()

    plot_filename = "oregon_monthly_avg_temperature_plot.png"
    plt.savefig(plot_filename, dpi=150)
    plt.close()
    faasr_log("Saved line plot as PNG")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperature_plot.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG plot file must exist locally after rendering")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperature_plot.png") or os.path.getsize("oregon_monthly_avg_temperature_plot.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG plot file must not be empty")
        raise SystemExit(1)
    # FORMAT check for valid_png_header on oregon_monthly_avg_temperature_plot.png (not yet implemented)
    if not (file_size_bytes >= 1024):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG must be at least 1KB, indicating a non-trivial rendered plot")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_monthly_avg_temperature.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file=plot_filename, remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded monthly average temperature plot to S3")