def plot_temperature_averages(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import matplotlib.pyplot as plt
    import numpy as np

    faasr_get_file(local_file="monthly_avg.csv", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os as _os
    if not os.path.exists("monthly_avg.csv"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file monthly_avg.csv must be successfully downloaded from S3 before processing")
        raise SystemExit(1)
    if not os.path.exists("monthly_avg.csv") or os.path.getsize("monthly_avg.csv") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Downloaded monthly_avg.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("monthly_avg.csv", nrows=1)
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file monthly_avg.csv must be a valid parseable CSV ({_e})")
        raise SystemExit(1)
    # CUSTOM check skipped (non-Python predicate): 'has_column:month' — CSV must contain a 'month' column with numeric month values (1-12)
    # CUSTOM check skipped (non-Python predicate): 'has_column:avg_temperature_c' — CSV must contain an 'avg_temperature_c' column with numeric temperature values
    # CUSTOM check skipped (non-Python predicate): 'column_values_in_range:month:1:12' — All values in the 'month' column must be integers between 1 and 12 inclusive
    # CUSTOM check skipped (non-Python predicate): 'column_is_numeric:avg_temperature_c' — All values in 'avg_temperature_c' column must be numeric (no NaN or non-numeric entries)
    # CUSTOM check skipped (non-Python predicate): 'row_count_gte:1' — CSV must contain at least one row of data to produce a meaningful plot
    # --- end requires ---
    faasr_log(f"Downloaded monthly average temperature CSV: {input1}")

    df = pd.read_csv("monthly_avg.csv")
    faasr_log(f"Loaded data with {len(df)} rows and columns: {list(df.columns)}")

    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }

    df = df.sort_values("month")
    df["month_label"] = df["month"].map(month_names)

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(
        df["month_label"],
        df["avg_temperature_c"],
        marker="o",
        linewidth=2,
        markersize=8,
        color="#2196F3",
        markerfacecolor="#1565C0",
        markeredgecolor="white",
        markeredgewidth=1.5
    )

    for _, row in df.iterrows():
        ax.annotate(
            f"{row['avg_temperature_c']:.1f}°C",
            xy=(row["month_label"], row["avg_temperature_c"]),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="#333333"
        )

    ax.set_xlabel("Month", fontsize=13, labelpad=10)
    ax.set_ylabel("Average Temperature (°C)", fontsize=13, labelpad=10)
    ax.set_title("Oregon Monthly Average Temperatures (January 2026)", fontsize=15, fontweight="bold", pad=15)

    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_ylim(df["avg_temperature_c"].min() - 2, df["avg_temperature_c"].max() + 3)

    plt.tight_layout()
    plt.savefig("temperature_plot.png", dpi=150, bbox_inches="tight")
    plt.close()
    faasr_log("Generated temperature line plot PNG")

    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("temperature_plot.png"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output PNG file temperature_plot.png must exist locally after matplotlib savefig")
        raise SystemExit(1)
    if not os.path.exists("temperature_plot.png") or os.path.getsize("temperature_plot.png") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file oregon_temperature_monthly_avg_plot.png uploaded to S3 must not be empty")
        raise SystemExit(1)
    # FORMAT check for png on temperature_plot.png (not yet implemented)
    # INPUTS_UNCHANGED: oregon_temperature_monthly_avg.csv (tracked at require time)
    # CUSTOM check skipped (non-Python predicate): 'log_contains:Downloaded monthly average temperature CSV' — Log must confirm successful download of the input CSV
    # CUSTOM check skipped (non-Python predicate): 'log_contains:Generated temperature line plot PNG' — Log must confirm that the temperature plot PNG was successfully generated
    # CUSTOM check skipped (non-Python predicate): 'log_contains:Uploaded plot to S3' — Log must confirm successful upload of the plot PNG to S3
    # CUSTOM check skipped (non-Python predicate): 'image_dimensions_gte:800x400' — Output PNG image should have dimensions consistent with figsize=(10,6) at dpi=150, approximately 1500x900 pixels
    # --- end promises ---
    faasr_put_file(local_file="temperature_plot.png", remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded plot to S3: {output1}")