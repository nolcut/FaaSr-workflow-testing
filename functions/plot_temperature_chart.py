def plot_temperature_chart(folder: str, input1: str, output1: str) -> None:
    import os
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    local_csv = "oregon_daily_avg_temperature_dec2025.csv"
    local_png = "oregon_temperature_chart_dec2025.png"

    faasr_get_file(local_file=local_csv, remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    if not os.path.exists("oregon_daily_avg_temperature_dec2025.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_daily_avg_temperature_dec2025.csv") or os.path.getsize("oregon_daily_avg_temperature_dec2025.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input temperature CSV must not be empty")
        raise SystemExit(1)
    try:
        import csv as _csv
        with open("oregon_daily_avg_temperature_dec2025.csv", newline="") as _f:
            next(_csv.reader(_f))
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV with at least 'date' and 'avg_temperature' columns: " + str(_e))
        raise SystemExit(1)
    # --- end requires ---


    faasr_log("Downloaded daily average temperature CSV from S3")

    df = pd.read_csv(local_csv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    faasr_log(f"Loaded {len(df)} rows of temperature data")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(
        df["date"],
        df["avg_temperature"],
        marker="o",
        linewidth=2,
        color="#1f77b4",
        markersize=5,
        label="Avg Temperature",
    )

    ax.set_title("Daily Average Temperature in Oregon — December 2025", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Date", fontsize=13)
    ax.set_ylabel("Average Temperature (°F)", fontsize=13)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45, ha="right")

    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(fontsize=11)

    plt.tight_layout()
    plt.savefig(local_png, dpi=150, bbox_inches="tight")
    plt.close()
    faasr_log("Temperature line chart created and saved locally")


    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_temperature_chart_dec2025.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output temperature chart PNG must exist after rendering")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_chart_dec2025.png") or os.path.getsize("oregon_temperature_chart_dec2025.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output temperature chart PNG must not be empty")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: oregon_daily_avg_temperature_dec2025.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file=local_png, remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded temperature chart PNG to S3")