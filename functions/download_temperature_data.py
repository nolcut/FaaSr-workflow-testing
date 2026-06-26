def download_temperature_data(folder: str, output1: str) -> None:
    # --- CONTRACT: requires ---
    import os as _os
    # --- end requires ---
    import requests
    import pandas as pd
    from datetime import datetime, timedelta

    faasr_log("Starting download of Oregon temperature data for January 2026")

    # Try to fetch data from NOAA Climate Data Online API
    # Using the NOAA CDO API v2 for daily temperature data in Oregon
    # Station: Portland, OR area (representative Oregon stations)
    # We'll try multiple approaches to get Oregon temperature data

    oregon_data = None

    # Approach 1: Try NOAA CDO API (requires token, may not be available)
    # Using a public NOAA endpoint for climate data
    try:
        faasr_log("Attempting to fetch data from NOAA CDO API")
        noaa_token = "YOUR_NOAA_TOKEN"  # placeholder
        headers = {"token": noaa_token}
        params = {
            "datasetid": "GHCND",
            "stationid": "GHCND:USW00024229",  # Portland International Airport
            "datatypeid": ["TMAX", "TMIN"],
            "startdate": "2026-01-01",
            "enddate": "2026-01-31",
            "units": "standard",
            "limit": 100
        }
        response = requests.get(
            "https://www.ncdc.noaa.gov/cdo-web/api/v2/data",
            headers=headers,
            params=params,
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            if "results" in data and len(data["results"]) > 0:
                records = data["results"]
                rows = {}
                for rec in records:
                    date = rec["date"][:10]
                    dtype = rec["datatype"]
                    val = rec["value"]
                    if date not in rows:
                        rows[date] = {"date": date}
                    rows[date][dtype] = val
                df = pd.DataFrame(list(rows.values()))
                if "TMAX" in df.columns and "TMIN" in df.columns:
                    df["temperature_f"] = (df["TMAX"] + df["TMIN"]) / 2.0
                elif "TMAX" in df.columns:
                    df["temperature_f"] = df["TMAX"]
                elif "TMIN" in df.columns:
                    df["temperature_f"] = df["TMIN"]
                df = df[["date", "temperature_f"]].sort_values("date").reset_index(drop=True)
                oregon_data = df
                faasr_log(f"Successfully fetched {len(df)} records from NOAA CDO API")
    except Exception as e:
        faasr_log(f"NOAA CDO API attempt failed: {e}")

    # Approach 2: Try Open-Meteo API (free, no token required)
    if oregon_data is None:
        try:
            faasr_log("Attempting to fetch data from Open-Meteo API")
            # Portland, Oregon coordinates: lat=45.5051, lon=-122.6750
            params = {
                "latitude": 45.5051,
                "longitude": -122.6750,
                "daily": ["temperature_2m_max", "temperature_2m_min"],
                "temperature_unit": "fahrenheit",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "timezone": "America/Los_Angeles"
            }
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                daily = data.get("daily", {})
                dates = daily.get("time", [])
                tmax = daily.get("temperature_2m_max", [])
                tmin = daily.get("temperature_2m_min", [])
                if dates:
                    rows = []
                    for i, date in enumerate(dates):
                        t_max = tmax[i] if i < len(tmax) and tmax[i] is not None else None
                        t_min = tmin[i] if i < len(tmin) and tmin[i] is not None else None
                        if t_max is not None and t_min is not None:
                            temp_avg = (t_max + t_min) / 2.0
                        elif t_max is not None:
                            temp_avg = t_max
                        elif t_min is not None:
                            temp_avg = t_min
                        else:
                            temp_avg = None
                        rows.append({"date": date, "temperature_f": temp_avg})
                    df = pd.DataFrame(rows)
                    df = df.dropna(subset=["temperature_f"]).reset_index(drop=True)
                    oregon_data = df
                    faasr_log(f"Successfully fetched {len(df)} records from Open-Meteo API")
            else:
                faasr_log(f"Open-Meteo returned status {response.status_code}")
        except Exception as e:
            faasr_log(f"Open-Meteo API attempt failed: {e}")

    # Approach 3: Try Open-Meteo archive API for historical/future data
    if oregon_data is None:
        try:
            faasr_log("Attempting to fetch data from Open-Meteo archive API")
            params = {
                "latitude": 45.5051,
                "longitude": -122.6750,
                "daily": ["temperature_2m_max", "temperature_2m_min"],
                "temperature_unit": "fahrenheit",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "timezone": "America/Los_Angeles"
            }
            response = requests.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params=params,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                daily = data.get("daily", {})
                dates = daily.get("time", [])
                tmax = daily.get("temperature_2m_max", [])
                tmin = daily.get("temperature_2m_min", [])
                if dates:
                    rows = []
                    for i, date in enumerate(dates):
                        t_max = tmax[i] if i < len(tmax) and tmax[i] is not None else None
                        t_min = tmin[i] if i < len(tmin) and tmin[i] is not None else None
                        if t_max is not None and t_min is not None:
                            temp_avg = (t_max + t_min) / 2.0
                        elif t_max is not None:
                            temp_avg = t_max
                        elif t_min is not None:
                            temp_avg = t_min
                        else:
                            temp_avg = None
                        rows.append({"date": date, "temperature_f": temp_avg})
                    df = pd.DataFrame(rows)
                    df = df.dropna(subset=["temperature_f"]).reset_index(drop=True)
                    if len(df) > 0:
                        oregon_data = df
                        faasr_log(f"Successfully fetched {len(df)} records from Open-Meteo archive API")
        except Exception as e:
            faasr_log(f"Open-Meteo archive API attempt failed: {e}")

    # Fallback: Generate synthetic Oregon January 2026 temperature data
    # based on historical Portland January averages (~39°F avg, range 33-46°F)
    if oregon_data is None:
        faasr_log("All API attempts failed. Generating synthetic Oregon January 2026 temperature data based on historical patterns.")
        import numpy as np

        dates = pd.date_range(start="2026-01-01", end="2026-01-31", freq="D")
        # Portland January historical: avg ~39°F, std ~6°F
        rng = np.random.default_rng(seed=42)
        temps = rng.normal(loc=39.0, scale=6.0, size=len(dates))
        # Add a mild cold-warm cycle typical of January
        cycle = 4.0 * np.sin(2 * np.pi * np.arange(len(dates)) / 14.0)
        temps = temps + cycle
        temps = np.clip(temps, 20.0, 58.0)

        df = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "temperature_f": temps.round(1)
        })
        oregon_data = df
        faasr_log(f"Generated {len(df)} synthetic temperature records for Oregon January 2026")

    # Save to local CSV
    local_file = "oregon_temperature_january_2026.csv"
    oregon_data.to_csv(local_file, index=False)
    faasr_log(f"Saved temperature data to local file: {local_file} ({len(oregon_data)} records)")

    # Upload to S3
    # --- CONTRACT: promises ---
    if hasattr(_faasr_log_buffer, "_entries") and any("error" in e.lower() for e in _faasr_log_buffer._entries):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Execution log contains error messages — possible silent failure")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_january_2026.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Local output file oregon_temperature_january_2026.csv must exist after data acquisition")
        raise SystemExit(1)
    if not os.path.exists("oregon_temperature_january_2026.csv") or os.path.getsize("oregon_temperature_january_2026.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file oregon_temperature_january_2026.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("oregon_temperature_january_2026.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file oregon_temperature_january_2026.csv must be valid CSV format ({_e})")
        raise SystemExit(1)
    if not (has_columns:date,temperature_f):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain exactly the columns 'date' and 'temperature_f'")
        raise SystemExit(1)
    if not (row_count_between:1:31):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV must contain between 1 and 31 rows (one per day in January 2026)")
        raise SystemExit(1)
    if not (date_column_format:YYYY-MM-DD):
        faasr_log("[PROMISE] CONTRACT VIOLATION: The 'date' column values must follow the ISO format YYYY-MM-DD")
        raise SystemExit(1)
    if not (date_range_within:2026-01-01:2026-01-31):
        faasr_log("[PROMISE] CONTRACT VIOLATION: All dates in the 'date' column must fall within January 2026 (2026-01-01 to 2026-01-31)")
        raise SystemExit(1)
    if not (column_no_nulls:temperature_f):
        faasr_log("[PROMISE] CONTRACT VIOLATION: The 'temperature_f' column must contain no null or NaN values")
        raise SystemExit(1)
    if not (column_numeric:temperature_f):
        faasr_log("[PROMISE] CONTRACT VIOLATION: The 'temperature_f' column must contain only numeric values")
        raise SystemExit(1)
    if not (column_range:temperature_f:-30:130):
        faasr_log("[PROMISE] CONTRACT VIOLATION: All temperature_f values must be physically plausible (between -30°F and 130°F)")
        raise SystemExit(1)
    if not (dates_unique):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Each date in the 'date' column must appear at most once (no duplicate dates)")
        raise SystemExit(1)
    if not (contains:Successfully uploaded Oregon January 2026 temperature data to S3):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must confirm successful S3 upload of the temperature data")
        raise SystemExit(1)
    if not (contains_one_of:Successfully fetched|Generated synthetic):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Log must confirm that temperature data was either fetched from an API or generated synthetically")
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
    faasr_log(f"Successfully uploaded Oregon January 2026 temperature data to S3: {folder}/{output1}")