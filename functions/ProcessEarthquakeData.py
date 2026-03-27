import json
import os
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


def ProcessEarthquakeData():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # Download inputs
    faasr_get_file(
        local_file="earthquake_data.json",
        remote_file="earthquake_data.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-6/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="_manifest.json",
        remote_file="_manifest.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-6/FetchEarthquakeData",
    )

    # --- Generated code ---

    faasr_log("Starting visual encoding computation for earthquake dataset")

    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    # Load earthquake data
    input_path = os.path.join(input_dir, "earthquake_data.json")
    faasr_log(f"Reading earthquake data from {input_path}")

    with open(input_path, "r") as f:
        data = json.load(f)

    metadata = data["metadata"]
    earthquakes = data["earthquakes"]

    faasr_log(f"Loaded {len(earthquakes)} earthquake records")
    faasr_log(f"Query date range: {metadata['query_start_date']} to {metadata['query_end_date']}")

    # Extract magnitudes and depths
    magnitudes = [eq["magnitude"] for eq in earthquakes]
    depths = [eq["depth"] for eq in earthquakes]

    # Compute min magnitude for marker size formula
    min_magnitude = min(magnitudes)
    faasr_log(f"Minimum magnitude: {min_magnitude}")

    # Compute min/max depth for color scaling
    min_depth = min(depths)
    max_depth = max(depths)
    faasr_log(f"Depth range: vmin={min_depth}, vmax={max_depth}")

    # Set up plasma colormap for depth encoding
    cmap = plt.get_cmap("plasma")
    norm = mcolors.Normalize(vmin=min_depth, vmax=max_depth)

    # Augment each earthquake record
    augmented_earthquakes = []
    for eq in earthquakes:
        magnitude = eq["magnitude"]
        depth = eq["depth"]

        # Compute marker size: size = 80 * (2 ** (magnitude - min_magnitude))
        marker_size = 80 * (2 ** (magnitude - min_magnitude))

        # Compute RGBA color from plasma colormap based on depth
        rgba = cmap(norm(depth))
        color_rgba = [round(rgba[0], 6), round(rgba[1], 6), round(rgba[2], 6), round(rgba[3], 6)]

        augmented_eq = {
            "magnitude": magnitude,
            "depth": depth,
            "latitude": eq["latitude"],
            "longitude": eq["longitude"],
            "marker_size": round(marker_size, 6),
            "color_rgba": color_rgba
        }
        augmented_earthquakes.append(augmented_eq)

    faasr_log(f"Computed marker sizes and color encodings for {len(augmented_earthquakes)} records")

    # Sample log for verification
    sample = augmented_earthquakes[0]
    faasr_log(f"Sample record: mag={sample['magnitude']}, depth={sample['depth']}, "
              f"marker_size={sample['marker_size']}, color_rgba={sample['color_rgba']}")

    # Build output structure
    output_data = {
        "metadata": {
            "query_start_date": metadata["query_start_date"],
            "query_end_date": metadata["query_end_date"],
            "total_records": len(augmented_earthquakes),
            "min_magnitude": min_magnitude,
            "depth_color_scaling": {
                "vmin": min_depth,
                "vmax": max_depth,
                "colormap": "plasma"
            }
        },
        "earthquakes": augmented_earthquakes
    }

    # Save augmented dataset
    output_path = os.path.join(output_dir, "earthquake_visual_encoding.json")
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    faasr_log(f"Saved augmented dataset to {output_path}")

    # Save manifest
    manifest = {
        "inputs": ["earthquake_data.json"],
        "outputs": [
            {
                "local_file": "earthquake_visual_encoding.json",
                "description": (
                    "Augmented earthquake dataset with visual encoding properties. "
                    "Each record includes original fields (magnitude, depth, latitude, longitude), "
                    "a computed marker_size using the formula 80 * (2 ** (magnitude - min_magnitude)), "
                    "and a color_rgba value derived from matplotlib's plasma colormap scaled by depth range. "
                    "Metadata includes query date range, min_magnitude, and depth color scaling parameters (vmin, vmax)."
                )
            }
        ],
        "packages": ["numpy", "matplotlib"]
    }

    manifest_path = os.path.join(output_dir, "_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    faasr_log("Visual encoding computation complete. Output ready for map rendering action.")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="earthquake_visual_encoding.json",
        remote_file="earthquake_visual_encoding.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/ProcessEarthquakeData",
    )
    faasr_put_file(
        local_file="ProcessEarthquakeData.py",
        remote_file="ProcessEarthquakeData.py",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/ProcessEarthquakeData",
    )
