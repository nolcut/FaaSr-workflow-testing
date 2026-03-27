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

    faasr_log("Starting USGS Earthquake API query")

    # Set up date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    faasr_log(f"Query date range: {start_str} to {end_str}")

    # Build API request
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "minmagnitude": 2.0,
        "minlatitude": 32,
        "maxlatitude": 49,
        "minlongitude": -125,
        "maxlongitude": -114,
        "starttime": start_str,
        "endtime": end_str
    }

    faasr_log("Sending request to USGS Earthquake API")

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        faasr_log(f"API response status: {response.status_code}")
    except Exception as e:
        faasr_log(f"Error fetching data from USGS API: {str(e)}")
        raise

    geojson_data = response.json()
    features = geojson_data.get("features", [])
    faasr_log(f"Total features retrieved: {len(features)}")

    # Extract fields from each feature
    records = []
    for feature in features:
        try:
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [None, None, None])
            mag = props.get("mag")
            depth = coords[2] if len(coords) > 2 else None
            lat = coords[1] if len(coords) > 1 else None
            lon = coords[0] if len(coords) > 0 else None
            records.append({
                "magnitude": mag,
                "depth": depth,
                "latitude": lat,
                "longitude": lon
            })
        except Exception as e:
            faasr_log(f"Error parsing feature: {str(e)}")
            continue

    faasr_log(f"Records before filtering: {len(records)}")

    # Build DataFrame and drop rows with null magnitude or depth
    df = pd.DataFrame(records, columns=["magnitude", "depth", "latitude", "longitude"])
    df_clean = df.dropna(subset=["magnitude", "depth"])

    faasr_log(f"Records after dropping nulls: {len(df_clean)}")

    # Prepare output with metadata
    output_data = {
        "metadata": {
            "query_start_date": start_str,
            "query_end_date": end_str,
            "total_records": len(df_clean)
        },
        "earthquakes": df_clean.to_dict(orient="records")
    }

    # Write output
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "earthquake_data.json")

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    faasr_log(f"Earthquake data saved to {output_path}")
    faasr_log(f"Done. {len(df_clean)} clean earthquake records saved.")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="earthquake_data.json",
        remote_file="earthquake_data.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/FetchEarthquakeData",
    )
    faasr_put_file(
        local_file="FetchEarthquakeData.py",
        remote_file="FetchEarthquakeData.py",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/FetchEarthquakeData",
    )
