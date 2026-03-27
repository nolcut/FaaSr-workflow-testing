import json
import os
import pandas as pd


def ProcessEarthquakeData():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # Download inputs
    faasr_get_file(
        local_file="earthquakes.geojson",
        remote_file="earthquakes.geojson",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-7/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="query_metadata.json",
        remote_file="query_metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-7/FetchEarthquakeData",
    )

    # --- Generated code ---

    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    faasr_log("Starting earthquake data parsing and enrichment")

    # Load GeoJSON
    geojson_path = os.path.join(input_dir, "earthquakes.geojson")
    with open(geojson_path, "r") as f:
        geojson_data = json.load(f)

    faasr_log(f"Loaded GeoJSON with {len(geojson_data.get('features', []))} features")

    # Load query metadata
    metadata_path = os.path.join(input_dir, "query_metadata.json")
    with open(metadata_path, "r") as f:
        query_metadata = json.load(f)

    query_starttime = query_metadata.get("query_starttime")
    query_endtime = query_metadata.get("query_endtime")
    faasr_log(f"Query period: {query_starttime} to {query_endtime}")

    # Parse features
    records = []
    for feature in geojson_data.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None, None])

        magnitude = props.get("mag")
        longitude = coords[0] if len(coords) > 0 else None
        latitude = coords[1] if len(coords) > 1 else None
        depth_km = coords[2] if len(coords) > 2 else None

        records.append({
            "magnitude": magnitude,
            "depth_km": depth_km,
            "latitude": latitude,
            "longitude": longitude
        })

    faasr_log(f"Parsed {len(records)} records from features")

    # Create DataFrame
    df = pd.DataFrame(records, columns=["magnitude", "depth_km", "latitude", "longitude"])

    # Drop rows where magnitude or depth_km is null
    df_clean = df.dropna(subset=["magnitude", "depth_km"]).copy()
    faasr_log(f"After dropping nulls: {len(df_clean)} records retained (dropped {len(df) - len(df_clean)})")

    # Compute derived columns
    min_magnitude = df_clean["magnitude"].min()
    faasr_log(f"Minimum magnitude in cleaned dataset: {min_magnitude}")

    df_clean["marker_size"] = 80 * (2 ** (df_clean["magnitude"] - min_magnitude))

    # depth_km retained as-is for colormap mapping (no normalization needed)
    # It's already present in the DataFrame

    event_count = len(df_clean)
    faasr_log(f"Total event count after filtering: {event_count}")

    # Save cleaned CSV
    csv_output_path = os.path.join(output_dir, "earthquakes_cleaned.csv")
    df_clean.to_csv(csv_output_path, index=False)
    faasr_log(f"Saved cleaned CSV to {csv_output_path}")

    # Save metadata JSON
    output_metadata = {
        "query_starttime": query_starttime,
        "query_endtime": query_endtime,
        "event_count": event_count
    }

    metadata_output_path = os.path.join(output_dir, "processing_metadata.json")
    with open(metadata_output_path, "w") as f:
        json.dump(output_metadata, f, indent=2)
    faasr_log(f"Saved processing metadata to {metadata_output_path}")

    faasr_log("Earthquake data parsing and enrichment complete")
    print(f"Processed {event_count} earthquake records")
    print(f"CSV saved to: {csv_output_path}")
    print(f"Metadata saved to: {metadata_output_path}")
    print(df_clean.head())
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="processing_metadata.json",
        remote_file="processing_metadata.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-7/ProcessEarthquakeData",
    )
    faasr_put_file(
        local_file="earthquakes_cleaned.csv",
        remote_file="earthquakes_cleaned.csv",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-7/ProcessEarthquakeData",
    )
