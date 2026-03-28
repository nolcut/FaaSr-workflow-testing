import json
import os
import datetime
import requests
import pandas as pd
from datetime import datetime, timedelta


def FetchEarthquakeData():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # --- Generated code ---

    faasr_log("Starting USGS earthquake data retrieval")

    # Compute date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    faasr_log(f"Querying earthquakes from {start_str} to {end_str}")

    # Build query parameters
    params = {
        "format": "geojson",
        "starttime": start_str,
        "endtime": end_str,
        "minmagnitude": 2.0,
        "minlatitude": 32,
        "maxlatitude": 49,
        "minlongitude": -125,
        "maxlongitude": -114,
    }

    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    faasr_log("Sending request to USGS FDSN Web Service")
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()

    geojson_data = response.json()
    features = geojson_data.get("features", [])
    faasr_log(f"Retrieved {len(features)} earthquake features from USGS")

    # Extract records
    records = []
    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [None, None, None])

        mag = props.get("mag")
        depth_km = coords[2] if len(coords) > 2 else None
        latitude = coords[1] if len(coords) > 1 else None
        longitude = coords[0] if len(coords) > 0 else None

        records.append({
            "magnitude": mag,
            "depth_km": depth_km,
            "latitude": latitude,
            "longitude": longitude,
        })

    df = pd.DataFrame(records, columns=["magnitude", "depth_km", "latitude", "longitude"])
    faasr_log(f"Total records before cleaning: {len(df)}")

    # Drop rows where magnitude or depth_km is null
    df_clean = df.dropna(subset=["magnitude", "depth_km"])
    faasr_log(f"Total records after dropping nulls: {len(df_clean)}")

    # Build output structure with metadata
    output_data = {
        "metadata": {
            "start_date": start_str,
            "end_date": end_str,
            "total_event_count": len(df_clean),
            "query_params": {
                "min_magnitude": 2.0,
                "min_latitude": 32,
                "max_latitude": 49,
                "min_longitude": -125,
                "max_longitude": -114,
            }
        },
        "earthquakes": df_clean.to_dict(orient="records")
    }

    # Save JSON output
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "earthquakes.json")
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    faasr_log(f"Saved earthquake data to {output_path}")

    # Also save CSV for convenience
    csv_path = os.path.join(output_dir, "earthquakes.csv")
    df_clean.to_csv(csv_path, index=False)
    faasr_log(f"Saved earthquake CSV to {csv_path}")

    # Save metadata separately
    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(output_data["metadata"], f, indent=2)

    faasr_log(f"Saved metadata to {meta_path}")
    faasr_log(f"Pipeline complete: {len(df_clean)} clean earthquake records from {start_str} to {end_str}")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="earthquakes.json",
        remote_file="earthquakes.json",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-13-static/{faasr_invocation_id()}/FetchEarthquakeData",
    )
    faasr_put_file(
        local_file="earthquakes.csv",
        remote_file="earthquakes.csv",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-13-static/{faasr_invocation_id()}/FetchEarthquakeData",
    )
    faasr_put_file(
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-13-static/{faasr_invocation_id()}/FetchEarthquakeData",
    )
