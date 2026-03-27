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
        local_file="earthquakes.csv",
        remote_file="earthquakes.csv",
        local_folder="/tmp/agent/input",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/input",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/FetchStateBoundaries",
    )

    # --- Generated code ---
    matplotlib.use('Agg')


    faasr_log("Starting earthquake map visualization")

    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    # Load metadata
    metadata_path = os.path.join(input_dir, "metadata.json")
    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    start_date = metadata["query_starttime"]
    end_date = metadata["query_endtime"]
    faasr_log(f"Metadata loaded: start={start_date}, end={end_date}")

    # Load earthquake CSV
    csv_path = os.path.join(input_dir, "earthquakes.csv")
    df = pd.read_csv(csv_path)
    faasr_log(f"Loaded {len(df)} earthquake records")

    # Clean: drop rows with null magnitude or depth
    df_clean = df.dropna(subset=["magnitude", "depth"])
    event_count = len(df_clean)
    faasr_log(f"After cleaning: {event_count} records remain")

    # Visual encoding
    depth_min = df_clean["depth"].min()
    depth_max = df_clean["depth"].max()
    mag_min = df_clean["magnitude"].min()

    faasr_log(f"Depth range: {depth_min} to {depth_max} km")
    faasr_log(f"Magnitude range: {mag_min} to {df_clean['magnitude'].max()}")

    # Marker sizes: 80 * 2^(mag - min_mag)
    marker_sizes = 80 * (2 ** (df_clean["magnitude"] - mag_min))

    # Colormap normalization for depth
    norm = mcolors.Normalize(vmin=depth_min, vmax=depth_max)
    cmap = cm.plasma

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_facecolor("#0d1b2a")

    # Scatter plot
    sc = ax.scatter(
        df_clean["longitude"],
        df_clean["latitude"],
        c=df_clean["depth"],
        s=marker_sizes,
        cmap=cmap,
        norm=norm,
        edgecolors="black",
        linewidths=0.3,
        zorder=3
    )

    # Load and overlay state boundaries
    geojson_path = os.path.join(input_dir, "western_states.geojson")
    states_gdf = gpd.read_file(geojson_path)
    faasr_log(f"Loaded state boundaries: {len(states_gdf)} features")

    for _, row in states_gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        if geom.geom_type == "Polygon":
            x, y = geom.exterior.xy
            ax.plot(x, y, color="#cccccc", linewidth=0.8, zorder=2)
            for interior in geom.interiors:
                xi, yi = interior.xy
                ax.plot(xi, yi, color="#cccccc", linewidth=0.8, zorder=2)
        elif geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                x, y = poly.exterior.xy
                ax.plot(x, y, color="#cccccc", linewidth=0.8, zorder=2)
                for interior in poly.interiors:
                    xi, yi = interior.xy
                    ax.plot(xi, yi, color="#cccccc", linewidth=0.8, zorder=2)

    # Grid
    ax.grid(True, linestyle="--", color="#cccccc", alpha=0.3, linewidth=0.5, zorder=1)

    # Set aspect and limits
    ax.set_aspect("equal")
    ax.set_xlim(-125, -114)
    ax.set_ylim(32, 49)

    # Colorbar
    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Depth (km)", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    # Legend for magnitude levels
    mag_levels = [2, 3, 4, 5, 6]
    legend_elements = []
    for m in mag_levels:
        size = 80 * (2 ** (m - mag_min))
        legend_elements.append(
            Line2D(
                [0], [0],
                marker="o",
                color="w",
                label=f"M{m}",
                markerfacecolor="gray",
                markeredgecolor="black",
                markeredgewidth=0.3,
                markersize=np.sqrt(size),
                linestyle="None"
            )
        )

    ax.legend(
        handles=legend_elements,
        loc="upper left",
        bbox_to_anchor=(1.15, 1.0),
        markerscale=0.4,
        labelspacing=1.2,
        handletextpad=1.0,
        framealpha=0.7,
        facecolor="#0d1b2a",
        edgecolor="#cccccc",
        labelcolor="white",
        title="Magnitude",
        title_fontsize=9
    )

    # Title
    title_str = f"Western US Earthquakes (M2.0+) | {start_date} to {end_date} | {event_count} events"
    ax.set_title(title_str, color="white", fontsize=11, pad=10)

    # Axis labels and tick colors
    ax.set_xlabel("Longitude", color="white")
    ax.set_ylabel("Latitude", color="white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#cccccc")

    fig.patch.set_facecolor("#0d1b2a")

    # Save
    output_path = os.path.join(output_dir, "western_us_earthquakes_map.png")
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()

    faasr_log(f"Map saved to {output_path}")
    faasr_log("Earthquake map visualization complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="western_us_earthquakes_map.png",
        remote_file="western_us_earthquakes_map.png",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/GenerateEarthquakeMap",
    )
