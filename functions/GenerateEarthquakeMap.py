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
        local_file="earthquakes.json",
        remote_file="earthquakes.json",
        local_folder="/tmp/agent/input",
        remote_folder=f"Western-US-Earthquake-Map-13-static/{faasr_invocation_id()}/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder=f"Western-US-Earthquake-Map-13-static/{faasr_invocation_id()}/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/input",
        remote_folder=f"Western-US-Earthquake-Map-13-static/{faasr_invocation_id()}/FetchStateBoundaries",
    )

    # --- Generated code ---
    matplotlib.use('Agg')


    faasr_log("Starting earthquake map visualization")

    # Paths
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    # Load earthquake data
    eq_path = os.path.join(input_dir, "earthquakes.json")
    with open(eq_path, "r") as f:
        eq_data = json.load(f)

    metadata = eq_data["metadata"]
    start_date = metadata["start_date"]
    end_date = metadata["end_date"]
    total_event_count = metadata["total_event_count"]

    earthquakes = pd.DataFrame(eq_data["earthquakes"])
    faasr_log(f"Loaded {len(earthquakes)} earthquake records")

    # Load state boundaries
    states_path = os.path.join(input_dir, "western_states.geojson")
    states_gdf = gpd.read_file(states_path)
    faasr_log("Loaded western states GeoJSON")

    # Step 1: Compute marker sizes
    min_magnitude = earthquakes["magnitude"].min()
    earthquakes["marker_size"] = 80 * (2 ** (earthquakes["magnitude"] - min_magnitude))

    faasr_log(f"Magnitude range: {min_magnitude:.2f} to {earthquakes['magnitude'].max():.2f}")
    faasr_log(f"Depth range: {earthquakes['depth_km'].min():.2f} to {earthquakes['depth_km'].max():.2f} km")

    # Step 2: Depth-based coloring setup
    depth_values = earthquakes["depth_km"].values
    cmap = cm.plasma
    norm = mcolors.Normalize(vmin=depth_values.min(), vmax=depth_values.max())

    # Step 3: Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    dark_navy = "#0d1b2a"
    fig.patch.set_facecolor(dark_navy)
    ax.set_facecolor(dark_navy)

    # Step 4: Plot state boundaries
    for geom in states_gdf.geometry:
        if geom is None:
            continue
        if geom.geom_type == "Polygon":
            polys = [geom]
        elif geom.geom_type == "MultiPolygon":
            polys = list(geom.geoms)
        else:
            polys = []
        for poly in polys:
            x, y = poly.exterior.xy
            ax.plot(x, y, color="#cccccc", linewidth=0.8)
            # Fill with no color (transparent)
            patch = plt.Polygon(list(zip(x, y)), closed=True, fill=False,
                                edgecolor="#cccccc", linewidth=0.8)
            ax.add_patch(patch)

    faasr_log("Plotted state boundaries")

    # Step 5: Dashed grid
    ax.grid(True, linestyle='--', color='#cccccc', alpha=0.3, linewidth=0.5)

    # Step 6: Scatter plot of earthquakes
    sc = ax.scatter(
        earthquakes["longitude"],
        earthquakes["latitude"],
        c=earthquakes["depth_km"],
        cmap="plasma",
        s=earthquakes["marker_size"],
        edgecolors="black",
        linewidths=0.3,
        zorder=5,
        norm=norm
    )

    faasr_log("Plotted earthquake scatter layer")

    # Step 7: Aspect and axis limits
    ax.set_aspect('equal')
    ax.set_xlim(-125, -114)
    ax.set_ylim(32, 49)

    # Style axis ticks and labels
    ax.tick_params(colors='white', labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor('#cccccc')

    ax.set_xlabel("Longitude", color="white", fontsize=10)
    ax.set_ylabel("Latitude", color="white", fontsize=10)

    # Step 8: Colorbar
    cbar = fig.colorbar(sc, ax=ax, pad=0.02, fraction=0.03)
    cbar.set_label("Depth (km)", color="white", fontsize=10)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    cbar.outline.set_edgecolor("#cccccc")

    # Step 9: Legend for magnitude
    legend_magnitudes = [2, 3, 4, 5, 6]
    legend_handles = []
    for mag in legend_magnitudes:
        size = 80 * (2 ** (mag - min_magnitude))
        handle = Line2D(
            [0], [0],
            marker='o',
            color='none',
            markerfacecolor='white',
            markeredgecolor='black',
            markeredgewidth=0.5,
            markersize=np.sqrt(size) * 0.4,
            label=f"M{mag}"
        )
        legend_handles.append(handle)

    legend = ax.legend(
        handles=legend_handles,
        title="Magnitude",
        loc='upper left',
        bbox_to_anchor=(1.15, 1.0),
        framealpha=0.2,
        facecolor=dark_navy,
        edgecolor="#cccccc",
        labelcolor="white",
        title_fontsize=9,
        fontsize=9,
        markerscale=0.4,
        labelspacing=1.2,
        handletextpad=1.0
    )
    legend.get_title().set_color("white")

    faasr_log("Added legend")

    # Step 10: Title
    title_str = f"Western US Earthquakes (M2.0+) | {start_date} to {end_date} | {total_event_count} events"
    ax.set_title(title_str, color="white", fontsize=13, fontweight='bold', pad=12)

    faasr_log(f"Title: {title_str}")

    # Step 11: Save figure
    output_path = os.path.join(output_dir, "western_us_earthquake_map.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()

    faasr_log(f"Saved earthquake map to {output_path}")
    faasr_log("Earthquake map visualization complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="western_us_earthquake_map.png",
        remote_file="western_us_earthquake_map.png",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-13-static/{faasr_invocation_id()}/GenerateEarthquakeMap",
    )
