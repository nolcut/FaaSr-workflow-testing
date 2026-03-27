import os


def BuildEarthquakeMap():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)

    # Download inputs
    faasr_get_file(
        local_file="earthquake_data_enriched.json",
        remote_file="earthquake_data_enriched.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/FetchStateBoundaries",
    )
    faasr_get_file(
        local_file="date_metadata.json",
        remote_file="date_metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="ProcessEarthquakeData.py",
        remote_file="ProcessEarthquakeData.py",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="_manifest.json",
        remote_file="_manifest.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/ProcessEarthquakeData",
    )

    # --- Generated code ---
    import json
    import os
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.lines import Line2D

    faasr_install("geopandas")
    import geopandas as gpd

    faasr_log("Starting earthquake map visualization")

    # Load enriched earthquake data
    eq_path = os.path.join(input_dir, "earthquake_data_enriched.json")
    faasr_log(f"Loading earthquake data from {eq_path}")
    with open(eq_path, "r") as f:
        eq_data = json.load(f)

    start_date = eq_data["start_date"]
    end_date = eq_data["end_date"]
    total_records = eq_data["total_records_after_cleaning"]
    records = eq_data["records"]

    faasr_log(f"Loaded {total_records} earthquake records from {start_date} to {end_date}")

    import pandas as pd
    df = pd.DataFrame(records)
    faasr_log(f"DataFrame columns: {list(df.columns)}, shape: {df.shape}")

    # Load state boundaries
    states_path = os.path.join(input_dir, "western_states.geojson")
    faasr_log(f"Loading state boundaries from {states_path}")
    states_gdf = gpd.read_file(states_path)
    faasr_log(f"Loaded {len(states_gdf)} state boundary features")

    # Compute min magnitude for legend sizing formula
    min_mag = df["magnitude"].min()
    faasr_log(f"Min magnitude in dataset: {min_mag}")

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor("#0d1b2a")
    ax.set_facecolor("#0d1b2a")

    # Plot state boundaries
    states_gdf.boundary.plot(ax=ax, edgecolor="#cccccc", linewidth=0.8)

    # Overlay dashed grid
    ax.grid(True, linestyle='--', alpha=0.3, linewidth=0.5, color='white')

    # Plot earthquake scatter
    scatter = ax.scatter(
        df["longitude"],
        df["latitude"],
        c=df["depth"],
        cmap="plasma",
        s=df["marker_size"],
        edgecolors="black",
        linewidths=0.3,
        zorder=5
    )

    # Set aspect ratio and axis limits
    ax.set_aspect("equal")
    ax.set_xlim(-125, -114)
    ax.set_ylim(32, 49)

    # Add colorbar
    cbar = fig.colorbar(scatter, ax=ax, pad=0.02, shrink=0.7)
    cbar.set_label("Depth (km)", color="white", fontsize=11)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    cbar.outline.set_edgecolor("white")

    # Style axes tick labels and spines
    ax.tick_params(colors="white", labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor("#cccccc")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")

    # Build magnitude legend
    legend_mags = [2, 3, 4, 5, 6]
    legend_handles = []
    for m in legend_mags:
        size = 80 * (2 ** (m - min_mag))
        handle = Line2D(
            [0], [0],
            marker='o',
            color='none',
            markerfacecolor='gray',
            markeredgecolor='black',
            markeredgewidth=0.5,
            markersize=np.sqrt(size) * 0.4,
            label=f"M{m}"
        )
        legend_handles.append(handle)

    legend = ax.legend(
        handles=legend_handles,
        loc='upper left',
        bbox_to_anchor=(1.15, 1.0),
        frameon=True,
        framealpha=0.3,
        facecolor="#0d1b2a",
        edgecolor="#cccccc",
        labelcolor="white",
        fontsize=9,
        title="Magnitude",
        title_fontsize=10,
        markerscale=0.4,
        labelspacing=1.2,
        handletextpad=1.0
    )
    legend.get_title().set_color("white")

    # Set figure title
    title_str = f"Western US Earthquakes (M2.0+) | {start_date} to {end_date} | {total_records} events"
    ax.set_title(title_str, color="white", fontsize=13, fontweight="bold", pad=12)

    # Axis labels
    ax.set_xlabel("Longitude", color="white", fontsize=10)
    ax.set_ylabel("Latitude", color="white", fontsize=10)

    # Save figure
    output_path = os.path.join(output_dir, "western_us_earthquake_map.png")
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    faasr_log(f"Saved earthquake map to {output_path}")

    # Verify file was saved
    if os.path.exists(output_path):
        size_kb = os.path.getsize(output_path) / 1024
        faasr_log(f"Map image saved successfully: {size_kb:.1f} KB")
    else:
        faasr_log("ERROR: Map image file was not created")

    faasr_log("Earthquake map visualization complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="western_us_earthquake_map.png",
        remote_file="western_us_earthquake_map.png",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/BuildEarthquakeMap",
    )
    faasr_put_file(
        local_file="BuildEarthquakeMap.py",
        remote_file="BuildEarthquakeMap.py",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/BuildEarthquakeMap",
    )
