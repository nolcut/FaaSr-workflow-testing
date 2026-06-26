def download_temperature_data(folder: str, input1: str, output1: str) -> None:
    import json
    import io
    import requests
    import pandas as pd

    # Download the request configuration from S3
    faasr_get_file(local_file="request_config.json", remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    import os
    if not os.path.exists("request_config.json"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input request_config.json must be downloaded from S3 before processing")
        raise SystemExit(1)
    if not os.path.exists("request_config.json") or os.path.getsize("request_config.json") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: request_config.json must not be empty")
        raise SystemExit(1)
    try:
        import json as _json; _json.loads(open("request_config.json").read())
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: request_config.json must be valid JSON ({_e})")
        raise SystemExit(1)
    # --- end requires ---
    faasr_log("Downloaded request configuration from S3")

    with open("request_config.json", "r") as f:
        config = json.load(f)

    # Extract configuration values with sensible defaults
    source_url = config.get("source_url") or config.get("url")
    if not source_url:
        raise Exception("Configuration error: missing 'source_url' (or 'url') in request_config.json")

    region = config.get("region", "Oregon")

    # Date range handling: support either a nested object or flat keys
    date_range = config.get("date_range", {})
    start_date = (
        config.get("start_date")
        or date_range.get("start")
        or date_range.get("start_date")
        or "2026-01-01"
    )
    end_date = (
        config.get("end_date")
        or date_range.get("end")
        or date_range.get("end_date")
        or "2026-01-31"
    )

    params = {
        "region": region,
        "start_date": start_date,
        "end_date": end_date,
    }

    # Allow additional params from config if provided
    extra_params = config.get("params")
    if isinstance(extra_params, dict):
        params.update(extra_params)

    faasr_log(f"Requesting temperature data: region='{region}', range {start_date} to {end_date}")

    # Issue HTTP GET request with error handling
    try:
        response = requests.get(source_url, params=params, timeout=120)
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error while requesting temperature data from {source_url}: {e}")

    # Validate HTTP response status
    if response.status_code != 200:
        raise Exception(
            f"Failed to download temperature data: HTTP {response.status_code} "
            f"from {source_url}. Response: {response.text[:500]}"
        )

    faasr_log(f"Received HTTP 200 response ({len(response.content)} bytes)")

    # Parse the returned CSV into a pandas DataFrame
    try:
        df = pd.read_csv(io.StringIO(response.text))
    except Exception as e:
        raise Exception(f"Failed to parse CSV response into DataFrame: {e}")

    # Validate expected columns
    required_columns = {"date", "temperature"}
    missing = required_columns - set(df.columns)
    if missing:
        raise Exception(
            f"Downloaded data is missing required columns: {sorted(missing)}. "
            f"Found columns: {list(df.columns)}"
        )

    if df.empty:
        raise Exception("Downloaded temperature data is empty (0 rows).")

    faasr_log(f"Parsed temperature data with {len(df)} rows and columns: {list(df.columns)}")

    # Write to local temp file and upload to S3
    df.to_csv("raw_temperature.csv", index=False)
    # --- CONTRACT: promises ---
    if not os.path.exists("raw_temperature.csv"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output raw_temperature.csv must be created")
        raise SystemExit(1)
    if not os.path.exists("raw_temperature.csv") or os.path.getsize("raw_temperature.csv") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output raw_temperature.csv must not be empty")
        raise SystemExit(1)
    try:
        import pandas as _pd; _pd.read_csv("raw_temperature.csv", nrows=1)
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output raw_temperature.csv must be a valid CSV file ({_e})")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: request_config.json (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file="raw_temperature.csv", remote_folder=folder, remote_file=output1)
    faasr_log(f"Uploaded raw_temperature.csv with {len(df)} records to S3 folder '{folder}'")