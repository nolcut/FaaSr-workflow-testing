def plot_temperature_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt

    faasr_get_file(local_file="oregon_monthly_averages.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("oregon_monthly_averages.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV file must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_averages.csv") or os.path.getsize("oregon_monthly_averages.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input CSV file must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_monthly_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV format ({_e})")
        raise SystemExit(1)
    # FORMAT check for has_column:year_month on oregon_monthly_averages.csv (not yet implemented)
    # FORMAT check for has_column:avg_temperature on oregon_monthly_averages.csv (not yet implemented)
    # --- end requires ---
    faasr_log("Downloaded monthly average temperature CSV from S3")

    df = pd.read_csv("oregon_monthly_averages.csv")
    faasr_log(f"Loaded {len(df)} rows from monthly averages CSV")

    unit = df["unit"].iloc[0] if "unit" in df.columns else "°F"

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(df["year_month"].astype(str), df["avg_temperature"], marker="o", linewidth=2, color="steelblue", label="Avg Temperature")

    ax.set_xlabel("Month", fontsize=12)
    ax.set_ylabel(f"Average Temperature ({unit})", fontsize=12)
    ax.set_title("Oregon Monthly Average Temperatures (January 2026)", fontsize=14)
    ax.grid(True, linestyle="--", alpha=0.7)
    ax.legend(fontsize=10)

    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    plt.savefig("oregon_temperature_plot.png", dpi=150)
    plt.close()
    faasr_log("Generated temperature line plot")

    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_temperature_plot.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG plot file must exist after generation")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_plot.png") or os.path.getsize("oregon_temperature_plot.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG plot file must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on oregon_temperature_plot.png (not yet implemented)
    # INPUTS_UNCHANGED: oregon_monthly_averages.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="oregon_temperature_plot.png", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded temperature plot PNG to S3")