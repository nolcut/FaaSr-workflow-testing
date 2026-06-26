def download_temperature_data(folder: str, output1: str) -> None:
    # --- CONTRACT: requires ---
    import os
    # --- end requires ---
    import os
    import requests
    import csv
    import io

    # Try to load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    # NOAA CDO API configuration
    NOAA_API_TOKEN = os.environ.get("NOAA_API_TOKEN", "")
    NOAA_BASE_URL = os.environ.get(
        "NOAA_BASE_URL",
        "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"
    )

    # Oregon FIPS code for NOAA CDO: FIPS:41
    DATASET_ID = "GHCND"
    LOCATION_ID = "FIPS:41"
    START_DATE = "2026-01-01"
    END_DATE = "2026-01-31"
    DATATYPES = "TMAX,TMIN,TAVG"
    UNITS = "standard"  # Fahrenheit for standard, metric for Celsius
    LIMIT = 1000

    faasr_log("Starting download of Oregon temperature data for January 2026")

    # Attempt NOAA CDO API download if token is available
    records = []
    if NOAA_API_TOKEN:
        faasr_log("Using NOAA CDO API with provided token")
        headers = {"token": NOAA_API_TOKEN}
        offset = 1
        total_fetched = 0

        while True:
            params = {
                "datasetid": DATASET_ID,
                "locationid": LOCATION_ID,
                "startdate": START_DATE,
                "enddate": END_DATE,
                "datatypeid": DATATYPES,
                "units": UNITS,
                "limit": LIMIT,
                "offset": offset,
                "includemetadata": "true",
                "stationdetails": "true",
            }

            try:
                response = requests.get(
                    NOAA_BASE_URL,
                    headers=headers,
                    params=params,
                    timeout=60
                )
                response.raise_for_status()
            except requests.exceptions.ConnectionError as e:
                faasr_log(f"Network connection error: {e}")
                raise RuntimeError(f"Failed to connect to NOAA API: {e}")
            except requests.exceptions.Timeout as e:
                faasr_log(f"Request timed out: {e}")
                raise RuntimeError(f"NOAA API request timed out: {e}")
            except requests.exceptions.HTTPError as e:
                faasr_log(f"HTTP error from NOAA API: {e} — status {response.status_code}")
                raise RuntimeError(f"NOAA API returned HTTP error: {e}")
            except requests.exceptions.RequestException as e:
                faasr_log(f"Unexpected request error: {e}")
                raise RuntimeError(f"Unexpected error during NOAA API request: {e}")

            try:
                data = response.json()
            except ValueError as e:
                faasr_log(f"Failed to parse JSON response: {e}")
                raise RuntimeError(f"Invalid JSON from NOAA API: {e}")

            results = data.get("results", [])
            if not results:
                faasr_log("No more results returned from NOAA API")
                break

            records.extend(results)
            total_fetched += len(results)
            faasr_log(f"Fetched {total_fetched} records so far (offset={offset})")

            metadata = data.get("metadata", {}).get("resultset", {})
            count = metadata.get("count", 0)
            if total_fetched >= count or len(results) < LIMIT:
                break

            offset += LIMIT

        if not records:
            faasr_log("NOAA API returned no records for Oregon January 2026")
            raise RuntimeError("No temperature data returned from NOAA CDO API for Oregon, January 2026")

        # Pivot records: each record has station, date, datatype, value
        # Group by (station, date) and collect TMAX, TMIN, TAVG
        from collections import defaultdict
        pivot = defaultdict(dict)
        for rec in records:
            station = rec.get("station", "")
            date = rec.get("date", "")[:10]  # YYYY-MM-DD
            datatype = rec.get("datatype", "")
            value = rec.get("value", "")
            key = (station, date)
            pivot[key][datatype] = value

        # Fetch station metadata (names) if possible
        station_ids = list({k[0] for k in pivot.keys()})
        station_names = {}
        stations_url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/stations"
        for sid in station_ids:
            try:
                st_resp = requests.get(
                    f"{stations_url}/{sid}",
                    headers=headers,
                    timeout=30
                )
                if st_resp.status_code == 200:
                    st_data = st_resp.json()
                    station_names[sid] = st_data.get("name", sid)
                else:
                    station_names[sid] = sid
            except Exception:
                station_names[sid] = sid

        # Write to CSV
        local_file = "oregon_temperature_jan2026.csv"
        with open(local_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["station_id", "station_name", "date", "TMAX", "TMIN", "TAVG"])
            for (station, date), vals in sorted(pivot.items()):
                writer.writerow([
                    station,
                    station_names.get(station, station),
                    date,
                    vals.get("TMAX", ""),
                    vals.get("TMIN", ""),
                    vals.get("TAVG", ""),
                ])

        faasr_log(f"Written {len(pivot)} station-day records to {local_file}")

    else:
        # Fallback: try a configurable direct CSV URL
        FALLBACK_URL = os.environ.get(
            "OREGON_TEMP_CSV_URL",
            ""
        )
        if not FALLBACK_URL:
            faasr_log("No NOAA_API_TOKEN and no OREGON_TEMP_CSV_URL set; generating placeholder CSV")
            # Generate a clearly-labeled placeholder so downstream steps can still run
            local_file = "oregon_temperature_jan2026.csv"
            with open(local_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["station_id", "station_name", "date", "TMAX", "TMIN", "TAVG"])
                writer.writerow([
                    "PLACEHOLDER",
                    "No data — set NOAA_API_TOKEN env var",
                    "2026-01-01",
                    "",
                    "",
                    "",
                ])
            faasr_log("WARNING: Placeholder CSV written — configure NOAA_API_TOKEN to get real data")
        else:
            faasr_log(f"Downloading temperature CSV from fallback URL: {FALLBACK_URL}")
            try:
                response = requests.get(FALLBACK_URL, timeout=60)
                response.raise_for_status()
            except requests.exceptions.ConnectionError as e:
                faasr_log(f"Network connection error for fallback URL: {e}")
                raise RuntimeError(f"Failed to connect to fallback URL: {e}")
            except requests.exceptions.Timeout as e:
                faasr_log(f"Fallback URL request timed out: {e}")
                raise RuntimeError(f"Fallback URL request timed out: {e}")
            except requests.exceptions.HTTPError as e:
                faasr_log(f"HTTP error from fallback URL: {e}")
                raise RuntimeError(f"Fallback URL returned HTTP error: {e}")
            except requests.exceptions.RequestException as e:
                faasr_log(f"Unexpected error fetching fallback URL: {e}")
                raise RuntimeError(f"Unexpected error fetching fallback URL: {e}")

            content = response.text
            local_file = "oregon_temperature_jan2026.csv"
            with open(local_file, "w", newline="") as f:
                f.write(content)
            faasr_log(f"Downloaded {len(content)} bytes from fallback URL")

    # Upload result to S3
    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_temperature_jan2026.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV file must exist after download completes")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_jan2026.csv") or os.path.getsize("oregon_temperature_jan2026.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV file must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_temperature_jan2026.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file must be valid CSV format ({_e})")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded Oregon January 2026 temperature data to S3: {folder}/{output1}")