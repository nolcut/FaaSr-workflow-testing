import json
import os
import datetime
import requests
from datetime import datetime, timedelta


def FetchEarthquakeData():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # --- Generated code ---

    faasr_log("Starting USGS Earthquake API query")

    # Compute date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    # Format as ISO 8601 strings (YYYY-MM-DD)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    faasr_log(f"Date range: {start_date_str} to {end_date_str}")

    # Build API request parameters
    params = {
        "format": "geojson",
        "minmagnitude": 2.0,
        "starttime": start_date_str,
        "endtime": end_date_str,
        "minlatitude": 32,
        "maxlatitude": 49,
        "minlongitude": -125,
        "maxlongitude": -114
    }

    api_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    faasr_log(f"Querying USGS API: {api_url} with params: {params}")

    try:
        response = requests.get(api_url, params=params, timeout=60)
        response.raise_for_status()
        geojson_data = response.json()
        faasr_log(f"Successfully retrieved GeoJSON response. Status code: {response.status_code}")
        feature_count = len(geojson_data.get("features", []))
        faasr_log(f"Number of earthquake features retrieved: {feature_count}")
    except requests.exceptions.RequestException as e:
        faasr_log(f"Error querying USGS API: {e}")
        raise

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save raw GeoJSON response
    geojson_output_path = os.path.join(output_dir, "earthquakes.geojson")
    with open(geojson_output_path, "w") as f:
        json.dump(geojson_data, f)
    faasr_log(f"Saved raw GeoJSON to {geojson_output_path}")

    # Save metadata file with date strings
    metadata = {
        "start_date": start_date_str,
        "end_date": end_date_str,
        "feature_count": feature_count,
        "api_url": api_url,
        "parameters": params
    }

    metadata_output_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    faasr_log(f"Saved metadata to {metadata_output_path}")

    faasr_log("USGS Earthquake API query completed successfully")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="earthquakes.geojson",
        remote_file="earthquakes.geojson",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-8/2026-03-26-19-59-26/outputs",
    )
    faasr_put_file(
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-8/2026-03-26-19-59-26/outputs",
    )
