def plot_temperature_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import numpy as np

    faasr_get_file(local_file="monthly_averages.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("monthly_averages.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file monthly_averages.csv must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("monthly_averages.csv") or os.path.getsize("monthly_averages.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file monthly_averages.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("monthly_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file monthly_averages.csv must be a valid CSV with at least one row and one column ({_e})")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log(f"Downloaded monthly averages file: {input1}")

    df = pd.read_csv("monthly_averages.csv")
    faasr_log(f"Loaded data with {len(df)} rows and columns: {list(df.columns)}")

    month_col = None
    for col in df.columns:
        if col.lower() in ("month", "month_name", "month_num", "date"):
            month_col = col
            break
    if month_col is None:
        month_col = df.columns[0]

    tmax_col = None
    tmin_col = None
    tavg_col = None
    for col in df.columns:
        cl = col.lower()
        if "tmax" in cl or "max" in cl:
            tmax_col = col
        elif "tmin" in cl or "min" in cl:
            tmin_col = col
        elif "tavg" in cl or "avg" in cl or "mean" in cl:
            tavg_col = col

    faasr_log(f"Using columns — month: {month_col}, tmax: {tmax_col}, tmin: {tmin_col}, tavg: {tavg_col}")

    fig, ax = plt.subplots(figsize=(10, 6))

    x = df[month_col].astype(str)
    x_positions = np.arange(len(x))

    if tmax_col:
        ax.plot(x_positions, df[tmax_col], marker="o", label="Avg High (°F)", color="#d62728", linewidth=2)
    if tmin_col:
        ax.plot(x_positions, df[tmin_col], marker="s", label="Avg Low (°F)", color="#1f77b4", linewidth=2)
    if tavg_col:
        ax.plot(x_positions, df[tavg_col], marker="^", label="Avg Mean (°F)", color="#2ca02c", linewidth=2, linestyle="--")

    ax.set_xticks(x_positions)
    ax.set_xticklabels(x, rotation=45, ha="right", fontsize=9)
    ax.set_xlabel("Month", fontsize=12)
    ax.set_ylabel("Temperature (°F)", fontsize=12)
    ax.set_title("Oregon Monthly Average Temperatures — January 2026", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())

    plt.tight_layout()
    plt.savefig("oregon_monthly_avg_temperatures.png", dpi=150)
    plt.close()
    faasr_log("Generated line plot PNG")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperatures.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG file oregon_monthly_avg_temperatures.png must exist after plot generation")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_avg_temperatures.png") or os.path.getsize("oregon_monthly_avg_temperatures.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG file oregon_monthly_avg_temperatures.png must not be empty")
        raise SystemExit(1)
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: No error or Error messages should appear in faasr_log output during execution")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: monthly_averages.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="oregon_monthly_avg_temperatures.png", remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded chart to S3: {output1}")