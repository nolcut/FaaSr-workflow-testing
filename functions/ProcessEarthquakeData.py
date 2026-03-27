import os


def ProcessEarthquakeData():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)

    # Download inputs
    faasr_get_file(
        local_file="earthquake_data_raw.json",
        remote_file="earthquake_data_raw.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="date_metadata.json",
        remote_file="date_metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="_manifest.json",
        remote_file="_manifest.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )

    # --- Generated code ---
    import json
    import os
    import pandas as pd
    import numpy as np

    faasr_log("Starting earthquake data preparation and enrichment step")

    # Load raw earthquake data
    raw_data_path = os.path.join(input_dir, "earthquake_data_raw.json")
    faasr_log(f"Reading raw earthquake data from {raw_data_path}")
    with open(raw_data_path, "r") as f:
        raw_data = json.load(f)

    # Load date metadata
    metadata_path = os.path.join(input_dir, "date_metadata.json")
    faasr_log(f"Reading date metadata from {metadata_path}")
    with open(metadata_path, "r") as f:
        date_metadata = json.load(f)

    faasr_log(f"Loaded {len(raw_data)} raw earthquake records")

    # Convert to DataFrame
    df = pd.DataFrame(raw_data)
    faasr_log(f"DataFrame columns: {list(df.columns)}")
    faasr_log(f"Initial record count: {len(df)}")

    # Clean: drop records with null/missing magnitude or depth
    df_clean = df.dropna(subset=["magnitude", "depth"])
    records_dropped = len(df) - len(df_clean)
    faasr_log(f"Dropped {records_dropped} records with null magnitude or depth")
    faasr_log(f"Clean record count: {len(df_clean)}")

    # Reset index after cleaning
    df_clean = df_clean.reset_index(drop=True)

    # Compute marker sizes using exponential scale
    min_magnitude = df_clean["magnitude"].min()
    faasr_log(f"Minimum magnitude in cleaned dataset: {min_magnitude}")
    df_clean["marker_size"] = 80 * (2 ** (df_clean["magnitude"] - min_magnitude))

    faasr_log(f"Marker size range: {df_clean['marker_size'].min():.2f} to {df_clean['marker_size'].max():.2f}")
    faasr_log(f"Depth range: {df_clean['depth'].min():.2f} to {df_clean['depth'].max():.2f} km")

    # Select final columns: magnitude, depth, latitude, longitude, marker_size
    output_df = df_clean[["magnitude", "depth", "latitude", "longitude", "marker_size"]]

    # Build enriched output structure
    enriched_output = {
        "start_date": date_metadata.get("start_date"),
        "end_date": date_metadata.get("end_date"),
        "total_records_after_cleaning": len(output_df),
        "query_parameters": date_metadata.get("query_parameters"),
        "records": output_df.to_dict(orient="records")
    }

    faasr_log(f"Enriched dataset contains {len(output_df)} records with columns: magnitude, depth, latitude, longitude, marker_size")

    # Save enriched dataset to output
    output_path = os.path.join(output_dir, "earthquake_data_enriched.json")
    with open(output_path, "w") as f:
        json.dump(enriched_output, f, indent=2)

    faasr_log(f"Saved enriched earthquake dataset to {output_path}")

    # Save manifest
    manifest = {
        "inputs": [
            "earthquake_data_raw.json",
            "date_metadata.json"
        ],
        "outputs": [
            {
                "local_file": "earthquake_data_enriched.json",
                "description": (
                    f"Cleaned and enriched earthquake dataset with {len(output_df)} records "
                    f"(after dropping nulls in magnitude/depth). Each record includes magnitude, "
                    f"depth, latitude, longitude, and marker_size (exponential scale: 80 * 2^(mag - min_mag)). "
                    f"Also includes date range metadata ({date_metadata.get('start_date')} to "
                    f"{date_metadata.get('end_date')}) and total cleaned record count."
                )
            }
        ],
        "packages": ["pandas", "numpy"]
    }

    manifest_path = os.path.join(output_dir, "_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    faasr_log("Manifest saved. Data preparation step complete.")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="ProcessEarthquakeData.py",
        remote_file="ProcessEarthquakeData.py",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/ProcessEarthquakeData",
    )
    faasr_put_file(
        local_file="earthquake_data_enriched.json",
        remote_file="earthquake_data_enriched.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/ProcessEarthquakeData",
    )
