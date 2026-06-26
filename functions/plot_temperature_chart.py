def plot_temperature_chart(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    faasr_get_file(local_file="daily_avg_temperature_jan2026.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("daily_avg_temperature_jan2026.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV file 'daily_avg_temperature_jan2026.csv' must exist before processing")
        raise SystemExit(1)
    if not os.path.exists("daily_avg_temperature_jan2026.csv") or os.path.getsize("daily_avg_temperature_jan2026.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV file 'daily_avg_temperature_jan2026.csv' must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("daily_avg_temperature_jan2026.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV format readable by pandas: " + str(_e))
        raise SystemExit(1)
    # FORMAT check for has_column:date on daily_avg_temperature_jan2026.csv (not yet implemented)
    # --- end requires ---
    faasr_log("Downloaded daily average temperature CSV from S3")

    df = pd.read_csv("daily_avg_temperature_jan2026.csv")
    faasr_log(f"Loaded CSV with {len(df)} rows and columns: {list(df.columns)}")

    if "date" not in df.columns:
        faasr_log("ERROR: 'date' column not found in CSV")
        raise ValueError("Input CSV must contain a 'date' column")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["day"] = df["date"].dt.day

    temp_col = None
    for col in df.columns:
        if "temp" in col.lower() or "avg" in col.lower():
            if col != "date":
                temp_col = col
                break
    if temp_col is None:
        for col in df.columns:
            if col not in ("date", "day"):
                temp_col = col
                break

    faasr_log(f"Using temperature column: {temp_col}")

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(df["day"], df[temp_col], color="steelblue", linewidth=2, marker="o", markersize=5, label="Avg Temperature (°C)")
    ax.fill_between(df["day"], df[temp_col], alpha=0.15, color="steelblue")

    ax.set_title("Daily Average Temperature — January 2026 (Oregon)", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Day of January 2026", fontsize=13)
    ax.set_ylabel("Average Temperature (°C)", fontsize=13)

    ax.set_xlim(1, 31)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(1))

    ax.grid(True, which="major", linestyle="--", linewidth=0.6, alpha=0.7)
    ax.grid(True, which="minor", linestyle=":", linewidth=0.4, alpha=0.4)

    ax.legend(fontsize=11)

    plt.xticks(rotation=45)
    plt.tight_layout()

    chart_local = "temperature_chart_january_2026.png"
    fig.savefig(chart_local, dpi=150, bbox_inches="tight")
    plt.close(fig)
    faasr_log("Generated temperature line chart PNG")

    # --- CONTRACT: promises ---
    if not os.path.exists("temperature_chart_january_2026.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG chart file 'temperature_chart_january_2026.png' must exist after processing")
        raise SystemExit(1)
    if not os.path.exists("temperature_chart_january_2026.png") or os.path.getsize("temperature_chart_january_2026.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG chart file 'temperature_chart_january_2026.png' must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on temperature_chart_january_2026.png (not yet implemented)
    # INPUTS_UNCHANGED: daily_avg_temperature_jan2026.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file=chart_local, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded chart as '{output1}' to S3 folder '{folder}'")