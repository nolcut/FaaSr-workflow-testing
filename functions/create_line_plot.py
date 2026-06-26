def create_line_plot(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

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
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file monthly_averages.csv must be a valid CSV ({_e})")
        raise SystemExit(1)
    # --- end requires ---

    df = pd.read_csv("monthly_averages.csv")
    faasr_log(f"Loaded monthly_averages.csv with {len(df)} rows")

    fig, ax = plt.subplots(figsize=(10, 6))

    if df.empty or "month" not in df.columns or "avg_temperature" not in df.columns:
        faasr_log("Input is empty or missing required columns; generating placeholder plot")
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", transform=ax.transAxes)
    else:
        ax.plot(df["month"], df["avg_temperature"], marker="o", linestyle="-")
        faasr_log(f"Plotted {len(df)} data points")

    ax.set_title("Monthly Average Temperatures")
    ax.set_xlabel("Month")
    ax.set_ylabel("Average Temperature")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig("monthly_averages_plot.png")
    plt.close(fig)

    # --- CONTRACT: promises ---
    if not os.path.exists("monthly_averages_plot.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output plot monthly_averages_plot.png must be created")
        raise SystemExit(1)
    if not os.path.exists("monthly_averages_plot.png") or os.path.getsize("monthly_averages_plot.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output plot monthly_averages_plot.png must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on monthly_averages_plot.png (not yet implemented)
    # INPUTS_UNCHANGED: monthly_averages.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="monthly_averages_plot.png", remote_folder=folder, remote_file=output1)
    faasr_log("Saved monthly_averages_plot.png to S3")