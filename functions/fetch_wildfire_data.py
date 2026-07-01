import os
import tempfile

import requests
import pandas as pd


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "raw_wildfire_data_2024.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output CSV of 2024 California wildfire incidents was not found in S3 after fetch_wildfire_data completed.")
        raise SystemExit(1)
# --- end contract helpers ---


def fetch_wildfire_data(folder: str, output1: str) -> None:
    """
    Fetch 2024 California wildfire incident data from the NIFC WFIGS
    (Wildland Fire Interagency Geospatial System) public ArcGIS REST service
    and upload the result as a CSV to S3.

    Data source: National Interagency Fire Center (NIFC) WFIGS –
      Incident Locations (FeatureServer, comprehensive historical archive).
    Public service; no authentication required.

    Confirmed endpoint:
      https://services3.arcgis.com/T4QMspbfLg3qTGWY/ArcGIS/rest/services/
      WFIGS_Incident_Locations/FeatureServer/0/query

    Field notes (verified against live service schema):
      - POOState uses the 'US-XX' format (e.g. 'US-CA' for California)
      - FireDiscoveryDateTime / ContainmentDateTime are epoch-millisecond values
      - ArcGIS SQL date predicates use the  timestamp 'YYYY-MM-DD HH:MM:SS' syntax
      - FinalAcres / IncidentSize both represent total acreage; IncidentSize is
        used as the primary column (FinalAcres is identical for closed incidents)
    """
    faasr_log(
        "fetch_wildfire_data: querying NIFC WFIGS Incident Locations "
        "for 2024 California wildfire incidents"
    )

    # -----------------------------------------------------------------------
    # NIFC WFIGS Incident Locations – comprehensive historical archive
    # (publicly accessible ArcGIS REST service, no credentials required)
    # -----------------------------------------------------------------------
    service_url = (
        "https://services3.arcgis.com/T4QMspbfLg3qTGWY/ArcGIS/rest/services/"
        "WFIGS_Incident_Locations/FeatureServer/0/query"
    )

    # State code in WFIGS is 'US-CA' (ISO 3166-2) not just 'CA'.
    # Date predicates use the ArcGIS SQL timestamp literal syntax.
    where_clause = (
        "POOState='US-CA' AND "
        "FireDiscoveryDateTime >= timestamp '2024-01-01 00:00:00' AND "
        "FireDiscoveryDateTime < timestamp '2025-01-01 00:00:00'"
    )

    # Attribute fields to retrieve (all confirmed present in the live schema)
    out_fields = [
        "IncidentName",
        "InitialLatitude",
        "InitialLongitude",
        "IncidentSize",       # total acreage (GIS-calculated or final report)
        "FinalAcres",         # final reported acres (same as IncidentSize when closed)
        "DiscoveryAcres",     # estimated acres at time of discovery
        "PercentContained",
        "FireDiscoveryDateTime",
        "ContainmentDateTime",
        "POOState",
        "POOCounty",
        "FireCause",
        "FireCauseGeneral",
        "IncidentTypeCategory",
        "UniqueFireIdentifier",
    ]

    # -----------------------------------------------------------------------
    # Paginate through all matching incident records
    # -----------------------------------------------------------------------
    records = []
    offset = 0
    page_size = 2000      # service maxRecordCount is 2000

    while True:
        params = {
            "where": where_clause,
            "outFields": ",".join(out_fields),
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "orderByFields": "FireDiscoveryDateTime ASC",
        }

        faasr_log(f"Requesting WFIGS records (offset={offset})")

        try:
            resp = requests.get(service_url, params=params, timeout=60)
        except requests.exceptions.RequestException as exc:
            faasr_log(f"Network error contacting NIFC WFIGS: {exc}")
            raise RuntimeError(
                f"Failed to reach NIFC WFIGS API at {service_url}: {exc}"
            ) from exc

        if resp.status_code != 200:
            faasr_log(
                f"NIFC WFIGS API returned HTTP {resp.status_code}: "
                f"{resp.text[:500]}"
            )
            raise RuntimeError(
                f"NIFC WFIGS API request failed with HTTP {resp.status_code}"
            )

        payload = resp.json()

        if "error" in payload:
            err = payload["error"]
            faasr_log(f"NIFC WFIGS API returned an error: {err}")
            raise RuntimeError(f"NIFC WFIGS API error: {err}")

        features = payload.get("features", [])
        faasr_log(f"Received {len(features)} features at offset {offset}")

        for feat in features:
            attrs = feat.get("attributes", {})

            # Prefer IncidentSize (GIS/final acreage); fall back to FinalAcres
            # then DiscoveryAcres if the others are absent.
            acres = (
                attrs.get("IncidentSize")
                or attrs.get("FinalAcres")
                or attrs.get("DiscoveryAcres")
            )

            records.append(
                {
                    "incident_name": attrs.get("IncidentName"),
                    "latitude": attrs.get("InitialLatitude"),
                    "longitude": attrs.get("InitialLongitude"),
                    "acres_burned": acres,
                    "percent_contained": attrs.get("PercentContained"),
                    "fire_discovery_datetime_ms": attrs.get("FireDiscoveryDateTime"),
                    "containment_datetime_ms": attrs.get("ContainmentDateTime"),
                    "state": attrs.get("POOState"),
                    "county": attrs.get("POOCounty"),
                    "fire_cause": attrs.get("FireCause") or attrs.get("FireCauseGeneral"),
                    "incident_type": attrs.get("IncidentTypeCategory"),
                    "unique_fire_id": attrs.get("UniqueFireIdentifier"),
                }
            )

        # Exit when the service returns fewer records than the page size
        if len(features) < page_size:
            break
        offset += page_size

    # -----------------------------------------------------------------------
    # Guard: fail loudly if no data was returned
    # -----------------------------------------------------------------------
    if not records:
        faasr_log(
            "NIFC WFIGS API returned 0 records for California (US-CA) 2024. "
            "Verify service availability and query parameters — "
            "do NOT fabricate data."
        )
        raise RuntimeError(
            "No 2024 California wildfire incident records retrieved from "
            f"NIFC WFIGS API ({service_url}). "
            "Check service URL, state code ('US-CA'), and date filter."
        )

    faasr_log(f"Total records retrieved: {len(records)}")

    # -----------------------------------------------------------------------
    # Build DataFrame and convert epoch-ms timestamps to ISO date strings
    # -----------------------------------------------------------------------
    df = pd.DataFrame(records)

    for ms_col, date_col in [
        ("fire_discovery_datetime_ms", "start_date"),
        ("containment_datetime_ms", "containment_date"),
    ]:
        if ms_col in df.columns:
            df[date_col] = pd.to_datetime(
                df[ms_col], unit="ms", utc=True, errors="coerce"
            ).dt.strftime("%Y-%m-%d")
            df = df.drop(columns=[ms_col])

    faasr_log(
        f"DataFrame ready: {df.shape[0]} rows x {df.shape[1]} columns "
        f"({list(df.columns)})"
    )

    # -----------------------------------------------------------------------
    # Write to a temp CSV, then upload to S3 via faasr_put_file
    # -----------------------------------------------------------------------
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False
    ) as tmp:
        tmp_path = tmp.name

    try:
        df.to_csv(tmp_path, index=False)
        faasr_log(
            f"Uploading {output1} ({len(df)} records) to folder '{folder}'"
        )
        faasr_put_file(
            local_file=tmp_path,
            remote_folder=folder,
            remote_file=output1,
        )
        faasr_log(f"Successfully uploaded {output1} to S3 folder '{folder}'")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---