import json
import os
import csv
import datetime
import requests
from datetime import datetime, timedelta


def FetchEarthquakeData():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # --- Generated code ---

    faasr_log("Starting USGS Earthquake data retrieval")

    # Compute date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)

    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    faasr_log(f"Query date range: {start_str} to {end_str}")

    # Build query URL
    base_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "starttime": start_str,
        "endtime": end_str,
        "minmagnitude": 2.0,
        "minlatitude": 32,
        "maxlatitude": 49,
        "minlongitude": -125,
        "maxlongitude": -114
    }

    faasr_log("Sending request to USGS FDSN Web Service")

    try:
        response = requests.get(base_url, params=params, timeout=60)
        response.raise_for_status()
        faasr_log(f"Response received, status code: {response.status_code}")
    except Exception as e:
        faasr_log(f"Error fetching data from USGS: {str(e)}")
        raise

    geojson_data = response.json()

    features = geojson_data.get("features", [])
    faasr_log(f"Number of earthquake features retrieved: {len(features)}")

    # Extract tabular data
    records = []
    for feature in features:
        coords = feature.get("geometry", {}).get("coordinates", [None, None, None])
        props = feature.get("properties", {})
        record = {
            "longitude": coords[0] if len(coords) > 0 else None,
            "latitude": coords[1] if len(coords) > 1 else None,
            "depth": coords[2] if len(coords) > 2 else None,
            "magnitude": props.get("mag"),
            "magType": props.get("magType"),
            "place": props.get("place"),
            "time": props.get("time")
        }
        records.append(record)

    faasr_log(f"Extracted {len(records)} records from GeoJSON features")

    # Build output GeoJSON with metadata
    output_geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "query_starttime": start_str,
            "query_endtime": end_str,
            "minmagnitude": 2.0,
            "bbox": {
                "minlatitude": 32,
                "maxlatitude": 49,
                "minlongitude": -125,
                "maxlongitude": -114
            },
            "count": len(features),
            "generated": geojson_data.get("metadata", {}).get("generated"),
            "title": geojson_data.get("metadata", {}).get("title", "USGS Earthquakes")
        },
        "features": features
    }

    # Also save CSV for easy downstream consumption

    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "earthquakes.csv")
    geojson_path = os.path.join(output_dir, "earthquakes.geojson")

    # Write CSV
    fieldnames = ["longitude", "latitude", "depth", "magnitude", "magType", "place", "time"]
    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    faasr_log(f"CSV saved to {csv_path}")

    # Write GeoJSON
    with open(geojson_path, "w") as gf:
        json.dump(output_geojson, gf, indent=2)

    faasr_log(f"GeoJSON saved to {geojson_path}")

    # Write metadata JSON for downstream agents
    metadata = {
        "query_starttime": start_str,
        "query_endtime": end_str,
        "earthquake_count": len(records),
        "csv_file": "earthquakes.csv",
        "geojson_file": "earthquakes.geojson"
    }

    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, "w") as mf:
        json.dump(metadata, mf, indent=2)

    faasr_log(f"Metadata saved to {metadata_path}")
    faasr_log("USGS Earthquake data retrieval and processing complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="earthquakes.csv",
        remote_file="earthquakes.csv",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/FetchEarthquakeData",
    )
    faasr_put_file(
        local_file="earthquakes.geojson",
        remote_file="earthquakes.geojson",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/FetchEarthquakeData",
    )
    faasr_put_file(
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/FetchEarthquakeData",
    )
