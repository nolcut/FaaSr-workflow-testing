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

    # Compute date range: past 30 days
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)

    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()

    faasr_log(f"Query time window: {start_date_str} to {end_date_str}")

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

    faasr_log(f"Sending request to USGS API: {api_url}")

    try:
        response = requests.get(api_url, params=params, timeout=60)
        response.raise_for_status()
        faasr_log(f"API response status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        faasr_log(f"ERROR: Failed to fetch data from USGS API: {e}")
        raise

    # Parse the GeoJSON response
    geojson_data = response.json()

    feature_count = len(geojson_data.get("features", []))
    faasr_log(f"Received {feature_count} earthquake features from API")

    # Inject query metadata into the GeoJSON metadata field if present, or add a custom key
    if "metadata" in geojson_data:
        geojson_data["metadata"]["query_starttime"] = start_date_str
        geojson_data["metadata"]["query_endtime"] = end_date_str
    else:
        geojson_data["query_metadata"] = {
            "query_starttime": start_date_str,
            "query_endtime": end_date_str
        }

    # Save the GeoJSON output
    os.makedirs(output_dir, exist_ok=True)
    geojson_output_path = os.path.join(output_dir, "earthquakes.geojson")

    with open(geojson_output_path, "w") as f:
        json.dump(geojson_data, f, indent=2)

    faasr_log(f"Saved GeoJSON with {feature_count} features to {geojson_output_path}")

    # Save companion metadata file for downstream steps
    metadata = {
        "query_starttime": start_date_str,
        "query_endtime": end_date_str,
        "feature_count": feature_count,
        "bounding_box": {
            "minlatitude": 32,
            "maxlatitude": 49,
            "minlongitude": -125,
            "maxlongitude": -114
        },
        "minmagnitude": 2.0,
        "api_url": api_url
    }

    metadata_output_path = os.path.join(output_dir, "query_metadata.json")
    with open(metadata_output_path, "w") as f:
        json.dump(metadata, f, indent=2)

    faasr_log(f"Saved query metadata to {metadata_output_path}")
    faasr_log("USGS Earthquake API query completed successfully")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="earthquakes.geojson",
        remote_file="earthquakes.geojson",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-7/FetchEarthquakeData",
    )
    faasr_put_file(
        local_file="query_metadata.json",
        remote_file="query_metadata.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-7/FetchEarthquakeData",
    )
