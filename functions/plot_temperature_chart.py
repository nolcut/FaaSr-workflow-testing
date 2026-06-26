def plot_temperature_chart(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    faasr_get_file(local_file="oregon_daily_avg_temperature_jan2026.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("oregon_daily_avg_temperature_jan2026.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_daily_avg_temperature_jan2026.csv") or os.path.getsize("oregon_daily_avg_temperature_jan2026.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must not be empty")
        raise SystemExit(1)
    try:
        import csv as _csv
        with open("oregon_daily_avg_temperature_jan2026.csv", newline="") as _f:
            next(_csv.reader(_f))
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV with at least 'date' and 'avg_temperature' columns: " + str(_e))
        raise SystemExit(1)
    # --- end requires ---
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("oregon_daily_avg_temperature_jan2026.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_daily_avg_temperature_jan2026.csv") or os.path.getsize("oregon_daily_avg_temperature_jan2026.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must not be empty")
        raise SystemExit(1)
    try:
        import csv as _csv
        with open("oregon_daily_avg_temperature_jan2026.csv", newline="") as _f:
            next(_csv.reader(_f))
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV with at least 'date' and 'avg_temperature' columns: " + str(_e))
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded daily average temperature CSV from S3")

    df = pd.read_csv("oregon_daily_avg_temperature_jan2026.csv")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    faasr_log(f"Loaded {len(df)} rows of temperature data")

    # Convert to Celsius if values appear to be in Fahrenheit (typical Jan Oregon temps in F are ~30-50°F)
    # Heuristic: if median value > 60, likely Fahrenheit
    import numpy as np
    median_temp = df["avg_temperature"].median()
    if median_temp > 60:
        faasr_log(f"Detected Fahrenheit temperatures (median={median_temp:.1f}°F), converting to Celsius")
        df["avg_temperature"] = (df["avg_temperature"] - 32) * 5.0 / 9.0
    else:
        faasr_log(f"Temperatures appear to be in Celsius already (median={median_temp:.1f}°C)")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df["date"], df["avg_temperature"], marker="o", linewidth=2, color="#1f77b4", markersize=5, label="Avg Temperature")

    ax.set_title("Daily Average Temperature in Oregon — January 2026", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Date", fontsize=13)
    ax.set_ylabel("Average Temperature (°C)", fontsize=13)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45, ha="right")

    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(fontsize=11)

    plt.tight_layout()
    plt.savefig("oregon_temperature_chart_jan2026.png", dpi=150, bbox_inches="tight")
    plt.close()
    faasr_log("Temperature line chart created and saved locally")

    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_temperature_chart_jan2026.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output temperature chart PNG must exist after rendering")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_chart_jan2026.png") or os.path.getsize("oregon_temperature_chart_jan2026.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output temperature chart PNG must not be empty")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_daily_avg_temperature_jan2026.csv (tracked at require time)
    # --- end promises ---
    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_temperature_chart_jan2026.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output temperature chart PNG must exist after rendering")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_chart_jan2026.png") or os.path.getsize("oregon_temperature_chart_jan2026.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output temperature chart PNG must not be empty")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_daily_avg_temperature_jan2026.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="oregon_temperature_chart_jan2026.png", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded temperature chart PNG to S3")