def download_temperature_data(folder: str, output1: str) -> None:
    import os
    import requests
    import pandas as pd

    faasr_log("Starting download of Oregon temperature data for December 2025")

    # NOAA Climate Data Online (CDO) API
    NOAA_BASE_URL = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"

    # Token must be provided via the NOAA_CDO_TOKEN environment variable.
    # Register for a free token at: https://www.ncdc.noaa.gov/cdo-web/token
    noaa_token = os.environ.get("NOAA_CDO_TOKEN", "")
    if not noaa_token:
        faasr_log(
            "ERROR: NOAA_CDO_TOKEN environment variable is not set. "
            "A valid NOAA CDO API token is required to download real data."
        )
        raise RuntimeError(
            "NOAA_CDO_TOKEN environment variable is required but not set. "
            "Obtain a free token at https://www.ncdc.noaa.gov/cdo-web/token"
        )

    # Known Oregon weather station IDs (GHCND network)
    oregon_stations = [
        "GHCND:USW00024229",  # Portland International Airport
        "GHCND:USW00024221",  # Eugene Airport
        "GHCND:USW00024232",  # Salem Airport
        "GHCND:USW00024225",  # Medford Airport
        "GHCND:USW00024284",  # Astoria Airport
        "GHCND:USW00024230",  # Pendleton Airport
        "GHCND:USW00024255",  # Redmond Airport
        "GHCND:USW00024243",  # North Bend Airport
        "GHCND:USW00094224",  # Klamath Falls
        "GHCND:USW00024227",  # Burns
    ]

    headers = {"token": noaa_token}
    records = []

    for station in oregon_stations:
        faasr_log(f"Fetching data for station {station}")
        params = {
            "datasetid": "GHCND",
            "stationid": station,
            "startdate": "2025-12-01",
            "enddate": "2025-12-31",
            # Request metric units so values are degrees Celsius (no manual scaling needed)
            "datatypeid": ["TMAX", "TMIN", "TAVG"],
            "units": "metric",
            "limit": 1000,
        }

        try:
            resp = requests.get(NOAA_BASE_URL, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            faasr_log(f"ERROR: NOAA API request failed for station {station}: {e}")
            raise

        data = resp.json()
        if "results" not in data:
            faasr_log(f"WARNING: No results returned for station {station} — skipping")
            continue

        daily = {}
        for item in data["results"]:
            date = item["date"][:10]          # "YYYY-MM-DDTHH:MM:SS" → "YYYY-MM-DD"
            dtype = item["datatype"]
            val = item["value"]               # already in °C with units=metric
            key = (station, date)
            if key not in daily:
                daily[key] = {
                    "station_id": station,
                    "date": date,
                    "tmax": None,
                    "tmin": None,
                    "tavg": None,
                }
            if dtype == "TMAX":
                daily[key]["tmax"] = val
            elif dtype == "TMIN":
                daily[key]["tmin"] = val
            elif dtype == "TAVG":
                daily[key]["tavg"] = val

        records.extend(daily.values())
        faasr_log(f"Station {station}: {len(daily)} daily records retrieved")

    if not records:
        faasr_log(
            "ERROR: No temperature records were retrieved from NOAA CDO API "
            "for any Oregon station in December 2025."
        )
        raise RuntimeError(
            "No temperature records retrieved from NOAA CDO API for Oregon, December 2025."
        )

    df = pd.DataFrame(records, columns=["station_id", "date", "tmax", "tmin", "tavg"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["station_id", "date"]).reset_index(drop=True)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    local_file = "oregon_temperature_dec2025_raw.csv"
    df.to_csv(local_file, index=False)

    faasr_log(
        f"Downloaded Oregon temperature dataset: {len(df)} records "
        f"across {df['station_id'].nunique()} stations"
    )

    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_temperature_dec2025_raw.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV file must exist after downloading and saving temperature data")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_dec2025_raw.csv") or os.path.getsize("oregon_temperature_dec2025_raw.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV file must contain at least one record of Oregon temperature data")
        raise SystemExit(1)
    try:
        import csv as _csv
        with open("oregon_temperature_dec2025_raw.csv", newline="") as _f:
            next(_csv.reader(_f))
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file must be a valid CSV with headers: station_id, date, tmax, tmin, tavg: " + str(_e))
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded raw temperature data to S3: {folder}/{output1}")