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
        remote_folder="Western-US-Earthquake-Map-8/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-8/FetchEarthquakeData",
    )

    # --- Generated code ---

    faasr_log("Starting earthquake data parsing and cleaning step")

    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    # Load the raw GeoJSON earthquake data
    geojson_path = os.path.join(input_dir, "earthquakes.geojson")
    faasr_log(f"Reading GeoJSON from {geojson_path}")

    with open(geojson_path, "r") as f:
        geojson_data = json.load(f)

    features = geojson_data.get("features", [])
    faasr_log(f"Total features found in GeoJSON: {len(features)}")

    # Load the metadata file
    metadata_path = os.path.join(input_dir, "metadata.json")
    faasr_log(f"Reading metadata from {metadata_path}")

    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    start_date = metadata.get("start_date", "")
    end_date = metadata.get("end_date", "")
    faasr_log(f"Query date range: {start_date} to {end_date}")

    # Parse each feature and extract relevant fields
    records = []
    for feature in features:
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [None, None, None])

        mag = props.get("mag", None)
        # Coordinates are [longitude, latitude, depth]
        longitude = coords[0] if len(coords) > 0 else None
        latitude = coords[1] if len(coords) > 1 else None
        depth = coords[2] if len(coords) > 2 else None

        records.append({
            "magnitude": mag,
            "depth": depth,
            "latitude": latitude,
            "longitude": longitude
        })

    faasr_log(f"Parsed {len(records)} records from GeoJSON features")

    # Assemble into a DataFrame
    df = pd.DataFrame(records, columns=["magnitude", "depth", "latitude", "longitude"])

    faasr_log(f"DataFrame shape before cleaning: {df.shape}")
    faasr_log(f"Null counts - magnitude: {df['magnitude'].isnull().sum()}, depth: {df['depth'].isnull().sum()}")

    # Drop rows with null/missing values in magnitude or depth
    df_clean = df.dropna(subset=["magnitude", "depth"])
    valid_count = len(df_clean)
    faasr_log(f"Valid earthquake events after cleaning: {valid_count}")

    # Save cleaned data as CSV
    csv_output_path = os.path.join(output_dir, "earthquakes_clean.csv")
    df_clean.to_csv(csv_output_path, index=False)
    faasr_log(f"Saved cleaned earthquake CSV to {csv_output_path}")

    # Also save as GeoJSON with point geometries
    geojson_features = []
    for _, row in df_clean.iterrows():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["longitude"], row["latitude"], row["depth"]]
            },
            "properties": {
                "magnitude": row["magnitude"],
                "depth": row["depth"],
                "latitude": row["latitude"],
                "longitude": row["longitude"]
            }
        }
        geojson_features.append(feature)

    clean_geojson = {
        "type": "FeatureCollection",
        "features": geojson_features
    }

    geojson_output_path = os.path.join(output_dir, "earthquakes_clean.geojson")
    with open(geojson_output_path, "w") as f:
        json.dump(clean_geojson, f)
    faasr_log(f"Saved cleaned earthquake GeoJSON to {geojson_output_path}")

    # Save updated metadata with valid event count
    updated_metadata = {
        "start_date": start_date,
        "end_date": end_date,
        "valid_event_count": valid_count
    }

    metadata_output_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_output_path, "w") as f:
        json.dump(updated_metadata, f, indent=2)
    faasr_log(f"Saved updated metadata to {metadata_output_path}")

    faasr_log(f"Earthquake parsing complete. {valid_count} valid events saved.")

    # Print summary
    print(f"Summary:")
    print(f"  Total features in GeoJSON: {len(features)}")
    print(f"  Valid events after cleaning: {valid_count}")
    print(f"  Date range: {start_date} to {end_date}")
    print(f"  Magnitude range: {df_clean['magnitude'].min():.1f} - {df_clean['magnitude'].max():.1f}")
    print(f"  Depth range: {df_clean['depth'].min():.1f} - {df_clean['depth'].max():.1f} km")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="earthquakes_clean.geojson",
        remote_file="earthquakes_clean.geojson",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-8/2026-03-26-19-59-26/outputs",
    )
    faasr_put_file(
        local_file="earthquakes_clean.csv",
        remote_file="earthquakes_clean.csv",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-8/2026-03-26-19-59-26/outputs",
    )
    faasr_put_file(
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-8/2026-03-26-19-59-26/outputs",
    )
