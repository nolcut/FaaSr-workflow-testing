def download_temperature_data(folder: str, output1: str) -> None:
    import requests
    import pandas as pd

    faasr_log("Starting download of Oregon temperature data for December 2025")

    # Read NOAA Climate Data Online (CDO) API token — raises if secret is absent
    noaa_token = faasr_secret("NOAA_CDO_TOKEN")

    NOAA_BASE_URL = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"

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
        faasr_log(f"Fetching December 2025 data for station {station}")
        offset = 1
        while True:
            params = {
                "datasetid": "GHCND",
                "stationid": station,
                "startdate": "2025-12-01",
                "enddate": "2025-12-31",
                "datatypeid": ["TMAX", "TMIN", "TAVG"],
                "units": "metric",
                "limit": 1000,
                "offset": offset,
            }
            resp = requests.get(NOAA_BASE_URL, headers=headers, params=params, timeout=30)
            if resp.status_code != 200:
                msg = f"NOAA CDO API error for station {station}: HTTP {resp.status_code} — {resp.text[:200]}"
                faasr_log(msg)
                raise RuntimeError(msg)

            data = resp.json()
            if "results" not in data:
                # Station has no records for this period — acceptable; continue to next
                faasr_log(f"No results for station {station} in December 2025")
                break

            daily = {}
            for item in data["results"]:
                date = item["date"][:10]
                dtype = item["datatype"]
                val = item["value"]
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

            # Paginate if there are more results
            metadata = data.get("metadata", {}).get("resultset", {})
            total = metadata.get("count", 0)
            if offset + 1000 > total:
                break
            offset += 1000

    if not records:
        msg = "No temperature records retrieved from NOAA CDO API for Oregon in December 2025"
        faasr_log(msg)
        raise RuntimeError(msg)

    df = pd.DataFrame(records, columns=["station_id", "date", "tmax", "tmin", "tavg"])

    # Derive tavg from tmax/tmin for stations that do not report TAVG directly
    mask = df["tavg"].isna() & df["tmax"].notna() & df["tmin"].notna()
    df.loc[mask, "tavg"] = ((df.loc[mask, "tmax"] + df.loc[mask, "tmin"]) / 2.0).round(1)

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["station_id", "date"]).reset_index(drop=True)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    local_file = "oregon_temperature_dec2025_raw.csv"
    df.to_csv(local_file, index=False)

    faasr_log(f"Retrieved {len(df)} records across {df['station_id'].nunique()} Oregon stations for December 2025")

    # --- CONTRACT: promises ---
    import os
    if not os.path.exists("oregon_temperature_dec2025_raw.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV file must exist after download and processing")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_dec2025_raw.csv") or os.path.getsize("oregon_temperature_dec2025_raw.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain at least one temperature record from Oregon stations")
        raise SystemExit(1)
    try:
        import csv as _csv
        with open("oregon_temperature_dec2025_raw.csv", newline="") as _f:
            next(_csv.reader(_f))
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file must be a valid CSV with columns: station_id, date, tmax, tmin, tavg: " + str(_e))
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded raw temperature data to S3: {folder}/{output1}")