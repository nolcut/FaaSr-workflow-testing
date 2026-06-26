def plot_temperature_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import numpy as np

    faasr_get_file(local_file="oregon_monthly_averages.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("oregon_monthly_averages.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input monthly averages CSV must exist after download from S3")
        raise SystemExit(1)
    if not os.path.exists("oregon_monthly_averages.csv") or os.path.getsize("oregon_monthly_averages.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input monthly averages CSV must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_monthly_averages.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file must be a valid CSV format readable by pandas ({_e})")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded monthly averages CSV from S3")

    df = pd.read_csv("oregon_monthly_averages.csv")
    faasr_log(f"Loaded monthly averages with {len(df)} rows")

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(
        df["year_month"].astype(str),
        df["avg_temperature"],
        marker="o",
        linewidth=2,
        color="#2196F3",
        markersize=6,
        markerfacecolor="#0D47A1",
        markeredgecolor="white",
        markeredgewidth=1.5,
        label="Avg Temperature (°F)"
    )

    ax.set_title("Oregon Monthly Average Temperatures — January 2026", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Month", fontsize=13, labelpad=10)
    ax.set_ylabel("Average Temperature (°F)", fontsize=13, labelpad=10)

    ax.grid(True, linestyle="--", alpha=0.6, color="gray")
    ax.set_axisbelow(True)

    plt.xticks(rotation=45, ha="right", fontsize=10)
    plt.yticks(fontsize=10)

    ax.legend(fontsize=11, loc="upper right")

    for x_val, y_val in zip(df["year_month"].astype(str), df["avg_temperature"]):
        ax.annotate(
            f"{y_val:.1f}",
            xy=(x_val, y_val),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color="#333333"
        )

    plt.tight_layout()
    plt.savefig("oregon_temperature_plot.png", dpi=150, bbox_inches="tight")
    plt.close()
    faasr_log("Generated temperature line plot PNG")

    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_temperature_plot.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output temperature plot PNG must exist after generation")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_plot.png") or os.path.getsize("oregon_temperature_plot.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output temperature plot PNG must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on oregon_temperature_plot.png (not yet implemented)
    # INPUTS_UNCHANGED: oregon_monthly_averages.csv (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="oregon_temperature_plot.png", remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded temperature plot PNG to S3")