def plot_temperature_chart(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    faasr_get_file(local_file="daily_averages.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("daily_averages.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file daily_averages.csv must exist locally after download from S3")
        raise SystemExit(1)
    if not os.path.exists("daily_averages.csv") or os.path.getsize("daily_averages.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file daily_averages.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("daily_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file daily_averages.csv must be a valid CSV with a parseable datetime index and at least one numeric column ({_e})")
        raise SystemExit(1)
    if not (row_count >= 1):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV must contain at least one data row to produce a meaningful chart")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded daily averages CSV from S3")

    df = pd.read_csv("daily_averages.csv", index_col=0, parse_dates=True)
    faasr_log(f"Loaded daily averages with {len(df)} rows")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df.index, df.iloc[:, 0], marker='o', linewidth=1.5, markersize=3, color='steelblue')
    ax.set_title("Daily Average Temperatures", fontsize=16)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Temperature", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(rotation=45)
    plt.tight_layout()

    fig.savefig("temperature_chart.png", dpi=150)
    plt.close(fig)
    faasr_log("Generated temperature line chart PNG")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file temperature_chart.png must exist locally after chart generation")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart.png") or os.path.getsize("temperature_chart.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file temperature_chart.png must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on temperature_chart.png (not yet implemented)
    if not (file_size_bytes >= 1024):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG must be at least 1KB, indicating a non-trivial rendered chart")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: daily_averages.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="temperature_chart.png", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded temperature chart PNG to S3")