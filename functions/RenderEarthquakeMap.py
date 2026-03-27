import json
import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors


def RenderEarthquakeMap():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # Download inputs
    faasr_get_file(
        local_file="earthquake_visual_encoding.json",
        remote_file="earthquake_visual_encoding.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-6/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-6/FetchStateBoundaries",
    )
    faasr_get_file(
        local_file="ProcessEarthquakeData.py",
        remote_file="ProcessEarthquakeData.py",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-6/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="earthquake_data.json",
        remote_file="earthquake_data.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-6/FetchEarthquakeData",
    )

    # --- Generated code ---
    matplotlib.use('Agg')

    faasr_log("Starting earthquake map visualization")

    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    # Load augmented earthquake dataset
    faasr_log("Loading earthquake visual encoding data")
    with open(os.path.join(input_dir, "earthquake_visual_encoding.json"), "r") as f:
        visual_data = json.load(f)

    metadata = visual_data["metadata"]
    earthquakes = visual_data["earthquakes"]

    start_date = metadata["query_start_date"]
    end_date = metadata["query_end_date"]
    n_events = len(earthquakes)
    vmin = metadata["depth_color_scaling"]["vmin"]
    vmax = metadata["depth_color_scaling"]["vmax"]
    min_magnitude = metadata["min_magnitude"]

    faasr_log(f"Loaded {n_events} earthquake records, date range {start_date} to {end_date}")
    faasr_log(f"Depth color scaling: vmin={vmin}, vmax={vmax}")

    # Load western states GeoJSON
    faasr_log("Loading western states GeoJSON")
    with open(os.path.join(input_dir, "western_states.geojson"), "r") as f:
        states_geojson = json.load(f)

    # Extract earthquake arrays
    lons = np.array([eq["longitude"] for eq in earthquakes])
    lats = np.array([eq["latitude"] for eq in earthquakes])
    depths = np.array([eq["depth"] for eq in earthquakes])
    magnitudes = np.array([eq["magnitude"] for eq in earthquakes])
    marker_sizes = np.array([eq["marker_size"] for eq in earthquakes])

    faasr_log("Creating figure and axes")

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))

    # Set background colors
    fig.patch.set_facecolor('#0d1b2a')
    ax.set_facecolor('#0d1b2a')

    # Helper function to plot GeoJSON geometries
    def plot_geometry(ax, geometry, color, linewidth):
        geom_type = geometry["type"]
        coords = geometry["coordinates"]

        if geom_type == "Polygon":
            for ring in coords:
                ring_arr = np.array(ring)
                ax.plot(ring_arr[:, 0], ring_arr[:, 1], color=color, linewidth=linewidth)
        elif geom_type == "MultiPolygon":
            for polygon in coords:
                for ring in polygon:
                    ring_arr = np.array(ring)
                    ax.plot(ring_arr[:, 0], ring_arr[:, 1], color=color, linewidth=linewidth)

    # Plot state boundaries
    faasr_log("Plotting state boundaries")
    for feature in states_geojson["features"]:
        geometry = feature["geometry"]
        plot_geometry(ax, geometry, color='#cccccc', linewidth=0.8)

    # Overlay dashed grid
    faasr_log("Adding grid")
    ax.grid(color='lightgray', linestyle='--', alpha=0.3, linewidth=0.5)

    # Plot earthquake scatter
    faasr_log("Plotting earthquake scatter")
    cmap = cm.get_cmap('plasma')
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    sc = ax.scatter(
        lons, lats,
        s=marker_sizes,
        c=depths,
        cmap='plasma',
        norm=norm,
        edgecolors='black',
        linewidths=0.3,
        zorder=5
    )

    # Set aspect and axis limits
    ax.set_aspect('equal')
    ax.set_xlim(-125, -114)
    ax.set_ylim(32, 49)

    # Style tick labels
    ax.tick_params(colors='#cccccc', labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor('#cccccc')

    # Add colorbar
    faasr_log("Adding colorbar")
    cbar = fig.colorbar(sc, ax=ax, pad=0.02, fraction=0.03)
    cbar.set_label('Depth (km)', color='#cccccc', fontsize=10)
    cbar.ax.yaxis.set_tick_params(color='#cccccc')
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color='#cccccc')
    cbar.outline.set_edgecolor('#cccccc')

    # Add legend with representative marker sizes for M2 through M6
    faasr_log("Adding legend")
    legend_handles = []
    for mag in range(2, 7):
        # Compute marker size using same exponential formula as ProcessEarthquakeData
        rep_size = 50 * np.exp(0.7 * (mag - min_magnitude))
        handle = ax.scatter(
            [], [],
            s=rep_size,
            c='white',
            edgecolors='black',
            linewidths=0.3,
            label=f'M{mag}'
        )
        legend_handles.append(handle)

    legend = ax.legend(
        handles=legend_handles,
        loc='upper left',
        bbox_to_anchor=(1.15, 1.0),
        markerscale=0.4,
        labelspacing=1.2,
        handletextpad=1.0,
        framealpha=0.2,
        facecolor='#0d1b2a',
        edgecolor='#cccccc',
        labelcolor='#cccccc',
        fontsize=9,
        title='Magnitude',
        title_fontsize=9
    )
    legend.get_title().set_color('#cccccc')

    # Set title
    title_str = f'Western US Earthquakes (M2.0+) | {start_date} to {end_date} | {n_events} events'
    ax.set_title(title_str, color='#cccccc', fontsize=11, pad=10)

    # Set axis label colors
    ax.xaxis.label.set_color('#cccccc')
    ax.yaxis.label.set_color('#cccccc')

    # Save figure
    output_path = os.path.join(output_dir, "western_us_earthquake_map.png")
    faasr_log(f"Saving figure to {output_path}")
    plt.savefig(
        output_path,
        dpi=150,
        bbox_inches='tight',
        facecolor=fig.get_facecolor()
    )
    plt.close(fig)

    faasr_log(f"Map saved successfully: {output_path}")
    faasr_log("Earthquake map visualization complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="western_us_earthquake_map.png",
        remote_file="western_us_earthquake_map.png",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/RenderEarthquakeMap",
    )
    faasr_put_file(
        local_file="RenderEarthquakeMap.py",
        remote_file="RenderEarthquakeMap.py",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/RenderEarthquakeMap",
    )
