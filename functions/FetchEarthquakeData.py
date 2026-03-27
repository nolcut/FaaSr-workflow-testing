import os


def FetchEarthquakeData():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)

    # --- Generated code ---
    import requests
    import json
    import os
    from datetime import datetime, timedelta

    faasr_log("Starting USGS Earthquake API query")

    # Define date range: past 30 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    faasr_log(f"Querying earthquakes from {start_date_str} to {end_date_str}")

    # API parameters
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

    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    try:
        faasr_log("Sending request to USGS Earthquake API")
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        faasr_log(f"API response status: {response.status_code}")
    except Exception as e:
        faasr_log(f"Error querying USGS API: {str(e)}")
        raise

    # Parse GeoJSON response
    geojson_data = response.json()
    features = geojson_data.get("features", [])
    faasr_log(f"Total earthquake features retrieved: {len(features)}")

    # Extract fields from each feature
    earthquake_records = []
    for feature in features:
        try:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coordinates = geometry.get("coordinates", [None, None, None])

            magnitude = properties.get("mag", None)
            longitude = coordinates[0] if len(coordinates) > 0 else None
            latitude = coordinates[1] if len(coordinates) > 1 else None
            depth = coordinates[2] if len(coordinates) > 2 else None

            record = {
                "magnitude": magnitude,
                "depth": depth,
                "latitude": latitude,
                "longitude": longitude
            }
            earthquake_records.append(record)
        except Exception as e:
            faasr_log(f"Error parsing feature: {str(e)}")
            continue

    faasr_log(f"Successfully parsed {len(earthquake_records)} earthquake records")

    # Prepare metadata
    date_metadata = {
        "start_date": start_date_str,
        "end_date": end_date_str,
        "total_records": len(earthquake_records),
        "query_parameters": {
            "minmagnitude": 2.0,
            "minlatitude": 32,
            "maxlatitude": 49,
            "minlongitude": -125,
            "maxlongitude": -114
        }
    }

    # Save outputs
    os.makedirs(output_dir, exist_ok=True)

    earthquake_output_path = os.path.join(output_dir, "earthquake_data_raw.json")
    with open(earthquake_output_path, "w") as f:
        json.dump(earthquake_records, f, indent=2)
    faasr_log(f"Saved raw earthquake dataset to {earthquake_output_path}")

    metadata_output_path = os.path.join(output_dir, "date_metadata.json")
    with open(metadata_output_path, "w") as f:
        json.dump(date_metadata, f, indent=2)
    faasr_log(f"Saved date range metadata to {metadata_output_path}")

    faasr_log("USGS Earthquake API query and data extraction complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="date_metadata.json",
        remote_file="date_metadata.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )
    faasr_put_file(
        local_file="FetchEarthquakeData.py",
        remote_file="FetchEarthquakeData.py",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )
    faasr_put_file(
        local_file="earthquake_data_raw.json",
        remote_file="earthquake_data_raw.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )
