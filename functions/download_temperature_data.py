def download_temperature_data(folder: str, output1: str) -> None:
    import os
    import time
    import requests
    import pandas as pd

    faasr_log("Starting download of Oregon December 2025 temperature data from NOAA CDO")

    # Raises if the secret is not configured — failing loudly is correct
    noaa_token = faasr_secret("NOAA_CDO_TOKEN")

    NOAA_BASE_URL = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"
    headers = {"token": noaa_token}

    # Well-known Oregon GHCND weather stations
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

    records = []

    for station in oregon_stations:
        faasr_log(f"Fetching December 2025 data for station: {station}")
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
                err_msg = (
                    f"NOAA CDO API returned HTTP {resp.status_code} for station "
                    f"{station}: {resp.text[:300]}"
                )
                faasr_log(err_msg)
                raise RuntimeError(err_msg)

            data = resp.json()
            result_list = data.get("results", [])

            if not result_list:
                # No (more) data for this station in the requested window
                break

            daily = {}
            for item in result_list:
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

            # Pagination: stop when we have consumed all reported results
            metadata = data.get("metadata", {}).get("resultset", {})
            total_count = int(metadata.get("count", 0))
            if offset + len(result_list) > total_count:
                break
            offset += len(result_list)

        # Respect NOAA CDO rate limit (5 requests/second)
        time.sleep(0.25)

    if not records:
        err_msg = (
            "No temperature records returned by NOAA CDO for Oregon December 2025. "
            "Verify that NOAA_CDO_TOKEN is valid and the stations have data for that period."
        )
        faasr_log(err_msg)
        raise RuntimeError(err_msg)

    df = pd.DataFrame(records, columns=["station_id", "date", "tmax", "tmin", "tavg"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["station_id", "date"]).reset_index(drop=True)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    faasr_log(
        f"Retrieved {len(df)} daily records from "
        f"{df['station_id'].nunique()} Oregon stations for December 2025"
    )

    local_file = "oregon_temperature_dec2025_raw.csv"
    df.to_csv(local_file, index=False)

    # --- CONTRACT: promises ---
    if not os.path.exists("oregon_temperature_dec2025_raw.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV file must exist locally before upload to S3")
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