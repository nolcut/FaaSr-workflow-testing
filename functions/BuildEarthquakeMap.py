import json
import os
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import geopandas as gpd


def BuildEarthquakeMap():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # Download inputs
    faasr_get_file(
        local_file="earthquakes_cleaned.csv",
        remote_file="earthquakes_cleaned.csv",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-7/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="processing_metadata.json",
        remote_file="processing_metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-7/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-7/FetchStateBoundaries",
    )

    # --- Generated code ---
    matplotlib.use('Agg')


    faasr_log("Starting earthquake map visualization")

    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    # Load earthquake CSV
    eq_path = os.path.join(input_dir, "earthquakes_cleaned.csv")
    faasr_log(f"Loading earthquake data from {eq_path}")
    df = pd.read_csv(eq_path)
    faasr_log(f"Loaded {len(df)} earthquake records")

    # Load metadata JSON
    meta_path = os.path.join(input_dir, "processing_metadata.json")
    faasr_log(f"Loading metadata from {meta_path}")
    with open(meta_path, "r") as f:
        metadata = json.load(f)

    start_date = metadata["query_starttime"]
    end_date = metadata["query_endtime"]
    event_count = metadata["event_count"]
    faasr_log(f"Metadata: {start_date} to {end_date}, {event_count} events")

    # Load state boundaries GeoJSON
    geojson_path = os.path.join(input_dir, "western_states.geojson")
    faasr_log(f"Loading state boundaries from {geojson_path}")
    states_gdf = gpd.read_file(geojson_path)
    faasr_log(f"Loaded {len(states_gdf)} state boundary features")

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor('#0d1b2a')
    ax.set_facecolor('#0d1b2a')

    # Plot state boundaries - outlines only, no fill
    states_gdf.boundary.plot(ax=ax, edgecolor='#cccccc', linewidth=0.8, facecolor='none')

    # Add grid overlay
    ax.grid(linestyle='--', alpha=0.3, linewidth=0.5, color='lightgray')

    # Plot earthquake scatter
    scatter = ax.scatter(
        df['longitude'],
        df['latitude'],
        c=df['depth_km'],
        s=df['marker_size'],
        cmap='plasma',
        edgecolors='black',
        linewidths=0.3,
        zorder=5
    )

    # Set aspect ratio and axis limits
    ax.set_aspect('equal')
    ax.set_xlim(-125, -114)
    ax.set_ylim(32, 49)

    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax, pad=0.02)
    cbar.set_label('Depth (km)', color='white', fontsize=11)
    cbar.ax.yaxis.set_tick_params(color='white')
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color='white')
    cbar.outline.set_edgecolor('white')

    # Style axes
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    for spine in ax.spines.values():
        spine.set_edgecolor('#cccccc')

    # Compute minimum magnitude for legend size formula
    min_mag = df['magnitude'].min()

    # Build legend with representative markers for M2-M6
    legend_handles = []
    for m in [2, 3, 4, 5, 6]:
        size = 80 * (2 ** (m - min_mag))
        handle = ax.scatter(
            [], [],
            s=size,
            c='gray',
            cmap='plasma',
            edgecolors='black',
            linewidths=0.3,
            label=f'M{m}'
        )
        legend_handles.append(handle)

    legend = ax.legend(
        handles=legend_handles,
        loc='upper left',
        bbox_to_anchor=(1.15, 1.0),
        markerscale=0.4,
        labelspacing=1.2,
        handletextpad=1.0,
        facecolor='#0d1b2a',
        edgecolor='#cccccc',
        labelcolor='white',
        title='Magnitude',
        title_fontsize=10
    )
    legend.get_title().set_color('white')

    # Set figure title
    title_str = f"Western US Earthquakes (M2.0+) | {start_date} to {end_date} | N={event_count} events"
    ax.set_title(title_str, color='white', fontsize=13, pad=12, fontweight='bold')

    # Axis labels
    ax.set_xlabel('Longitude', color='white', fontsize=10)
    ax.set_ylabel('Latitude', color='white', fontsize=10)

    # Save figure
    output_path = os.path.join(output_dir, "earthquake_map.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    faasr_log(f"Saved earthquake map to {output_path}")
    faasr_log("Earthquake map visualization complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="earthquake_map.png",
        remote_file="earthquake_map.png",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-7/BuildEarthquakeMap",
    )
