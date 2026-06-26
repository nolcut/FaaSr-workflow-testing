def plot_temperature_chart(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    faasr_get_file(local_file="daily_avg_temperature_jan2026.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("daily_avg_temperature_jan2026.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV file must exist before processing")
        raise SystemExit(1)
    if not os.path.exists("daily_avg_temperature_jan2026.csv") or os.path.getsize("daily_avg_temperature_jan2026.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV file must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("daily_avg_temperature_jan2026.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV format: " + str(_e))
        raise SystemExit(1)
    # FORMAT check for has_column:date on daily_avg_temperature_jan2026.csv (not yet implemented)
    # FORMAT check for has_column:avg_temperature_c on daily_avg_temperature_jan2026.csv (not yet implemented)
    # --- end requires ---
    faasr_log("Downloaded daily average temperature data from S3")

    df = pd.read_csv("daily_avg_temperature_jan2026.csv")
    faasr_log(f"Loaded temperature data with {len(df)} rows")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["day"] = df["date"].dt.day

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(df["day"], df["avg_temperature_c"], color="steelblue", linewidth=2, marker="o", markersize=5, label="Avg Temperature (°C)")

    ax.set_title("Daily Average Temperatures — January 2026 (Oregon)", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Day of January 2026", fontsize=13)
    ax.set_ylabel("Average Temperature (°C)", fontsize=13)

    ax.set_xlim(1, 31)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(1))

    ax.grid(True, which="major", linestyle="--", alpha=0.5)
    ax.legend(fontsize=11)

    min_temp = df["avg_temperature_c"].min()
    max_temp = df["avg_temperature_c"].max()
    min_day = df.loc[df["avg_temperature_c"].idxmin(), "day"]
    max_day = df.loc[df["avg_temperature_c"].idxmax(), "day"]

    ax.annotate(f"Min: {min_temp:.1f}°C", xy=(min_day, min_temp),
                xytext=(min_day + 1, min_temp - 0.8),
                arrowprops=dict(arrowstyle="->", color="blue"),
                fontsize=9, color="blue")

    ax.annotate(f"Max: {max_temp:.1f}°C", xy=(max_day, max_temp),
                xytext=(max_day + 1, max_temp + 0.5),
                arrowprops=dict(arrowstyle="->", color="red"),
                fontsize=9, color="red")

    plt.tight_layout()
    plt.savefig("temperature_chart_january_2026.png", dpi=150, bbox_inches="tight")
    plt.close()
    faasr_log("Generated temperature line chart PNG")

    # --- CONTRACT: promises ---
    if not os.path.exists("temperature_chart_january_2026.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG chart file must exist after processing")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart_january_2026.png") or os.path.getsize("temperature_chart_january_2026.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG chart file must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on temperature_chart_january_2026.png (not yet implemented)
    # INPUTS_UNCHANGED: daily_avg_temperature_jan2026.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="temperature_chart_january_2026.png", remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded temperature chart to S3 as '{output1}'")