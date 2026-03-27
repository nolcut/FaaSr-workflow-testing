import json
import os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
import geopandas as gpd


def GenerateEarthquakeMap():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # Download inputs
    faasr_get_file(
        local_file="earthquakes_clean.csv",
        remote_file="earthquakes_clean.csv",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-8/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-8/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-8/FetchStateBoundaries",
    )

    # --- Generated code ---
    matplotlib.use('Agg')


    faasr_log("Starting western US earthquake map visualization")

    # Paths
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    # 1. Load earthquake data and metadata
    faasr_log("Loading earthquake data and metadata")
    eq_df = pd.read_csv(os.path.join(input_dir, "earthquakes_clean.csv"))
    faasr_log(f"Loaded {len(eq_df)} earthquake records")

    with open(os.path.join(input_dir, "metadata.json"), "r") as f:
        metadata = json.load(f)

    start_date = metadata["start_date"]
    end_date = metadata["end_date"]
    valid_event_count = metadata["valid_event_count"]
    faasr_log(f"Metadata: {start_date} to {end_date}, {valid_event_count} events")

    # 2. Load state boundary GeoJSON
    faasr_log("Loading state boundary GeoJSON")
    states_gdf = gpd.read_file(os.path.join(input_dir, "western_states.geojson"))
    faasr_log(f"Loaded {len(states_gdf)} state geometries")

    # 3. Compute marker sizes using exponential scale
    min_magnitude = eq_df["magnitude"].min()
    marker_sizes = 80 * (2 ** (eq_df["magnitude"] - min_magnitude))
    faasr_log(f"Computed marker sizes. Min mag: {min_magnitude:.2f}, size range: {marker_sizes.min():.1f} - {marker_sizes.max():.1f}")

    # 4. Map depth values to plasma colormap
    depth_min = eq_df["depth"].min()
    depth_max = eq_df["depth"].max()
    faasr_log(f"Depth range: {depth_min:.2f} to {depth_max:.2f} km")

    norm = mcolors.Normalize(vmin=depth_min, vmax=depth_max)
    cmap = cm.get_cmap("plasma")
    colors = cmap(norm(eq_df["depth"].values))

    # 5. Create figure with dark navy background
    faasr_log("Creating figure")
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor("#0d1b2a")
    ax.set_facecolor("#0d1b2a")

    # 6. Plot state boundaries
    faasr_log("Plotting state boundaries")
    states_gdf.boundary.plot(ax=ax, edgecolor="#cccccc", linewidth=0.8, facecolor="none")

    # 7. Overlay dashed grid
    ax.grid(True, linestyle="--", color="#cccccc", alpha=0.3, linewidth=0.5)

    # 8. Plot earthquake scatter
    faasr_log("Plotting earthquake scatter")
    sc = ax.scatter(
        eq_df["longitude"],
        eq_df["latitude"],
        s=marker_sizes,
        c=eq_df["depth"],
        cmap="plasma",
        norm=norm,
        edgecolors="black",
        linewidths=0.3,
        zorder=5
    )

    # 9. Equal aspect ratio and axis limits
    ax.set_aspect("equal")
    ax.set_xlim(-125, -114)
    ax.set_ylim(32, 49)

    # Style tick labels
    ax.tick_params(colors="#cccccc", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#cccccc")

    # 10. Add colorbar
    faasr_log("Adding colorbar")
    cbar = plt.colorbar(sc, ax=ax, pad=0.02, fraction=0.03)
    cbar.set_label("Depth (km)", color="#cccccc", fontsize=10)
    cbar.ax.yaxis.set_tick_params(color="#cccccc", labelcolor="#cccccc")
    cbar.outline.set_edgecolor("#cccccc")

    # 11. Add legend with representative marker sizes
    faasr_log("Adding legend")
    legend_magnitudes = [2, 3, 4, 5, 6]
    legend_elements = []
    for mag in legend_magnitudes:
        size = 80 * (2 ** (mag - min_magnitude))
        legend_elements.append(
            Line2D(
                [0], [0],
                marker="o",
                color="none",
                markerfacecolor="white",
                markeredgecolor="black",
                markeredgewidth=0.5,
                markersize=np.sqrt(size),
                label=f"M{mag}"
            )
        )

    legend = ax.legend(
        handles=legend_elements,
        loc="upper left",
        bbox_to_anchor=(1.15, 1.0),
        markerscale=0.4,
        labelspacing=1.2,
        handletextpad=1.0,
        framealpha=0.3,
        facecolor="#0d1b2a",
        edgecolor="#cccccc",
        labelcolor="#cccccc",
        fontsize=9,
        title="Magnitude",
        title_fontsize=9
    )
    legend.get_title().set_color("#cccccc")

    # 12. Set title
    title_str = f"Western US Earthquakes (M2.0+) | {start_date} to {end_date} | {valid_event_count} events"
    ax.set_title(title_str, color="#cccccc", fontsize=12, pad=12)

    ax.set_xlabel("Longitude", color="#cccccc", fontsize=9)
    ax.set_ylabel("Latitude", color="#cccccc", fontsize=9)

    # 13. Save figure
    output_path = os.path.join(output_dir, "western_us_earthquakes_map.png")
    faasr_log(f"Saving figure to {output_path}")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    faasr_log("Map visualization saved successfully")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="western_us_earthquakes_map.png",
        remote_file="western_us_earthquakes_map.png",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-8/2026-03-26-19-59-26/outputs",
    )
