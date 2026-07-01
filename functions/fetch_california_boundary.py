import json
import os
import tempfile

import requests


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "california_state_boundary.geojson" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: California state boundary GeoJSON was not uploaded to S3 after fetching from TIGERweb")
        raise SystemExit(1)
    if "california_county_boundaries.geojson" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: California county boundaries GeoJSON was not uploaded to S3 after fetching from TIGERweb")
        raise SystemExit(1)
# --- end contract helpers ---


def fetch_california_boundary(folder: str, output1: str, output2: str) -> None:
    """
    Download California state boundary and all California county boundary
    GeoJSON data from the US Census Bureau TIGERweb REST services and
    upload both files to S3.

    Data source: US Census Bureau TIGERweb REST MapService – State_County
      https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer
      Layer 0 – States
      Layer 1 – Counties
    Public service; no authentication required.
    """

    # California identifiers
    CA_STUSAB = "CA"       # 2-letter postal abbreviation used in state layer
    CA_STATE_FIPS = "06"   # FIPS code used in county layer

    TIGERWEB_BASE = (
        "https://tigerweb.geo.census.gov/arcgis/rest/services/"
        "TIGERweb/State_County/MapServer"
    )

    # ------------------------------------------------------------------
    # 1. Fetch California state boundary  (MapServer layer 0 = States)
    # ------------------------------------------------------------------
    faasr_log(
        "fetch_california_boundary: fetching California state boundary "
        "from US Census Bureau TIGERweb"
    )

    state_url = f"{TIGERWEB_BASE}/0/query"
    state_params = {
        "where": f"STUSAB='{CA_STUSAB}'",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
    }

    try:
        state_resp = requests.get(state_url, params=state_params, timeout=60)
    except requests.exceptions.RequestException as exc:
        faasr_log(f"Network error fetching California state boundary: {exc}")
        raise RuntimeError(
            f"Failed to reach TIGERweb state boundary service at {state_url}: {exc}"
        ) from exc

    if state_resp.status_code != 200:
        faasr_log(
            f"TIGERweb state boundary service returned HTTP "
            f"{state_resp.status_code}: {state_resp.text[:500]}"
        )
        raise RuntimeError(
            f"TIGERweb state boundary request failed with HTTP "
            f"{state_resp.status_code}"
        )

    state_geojson = state_resp.json()

    # A valid GeoJSON FeatureCollection has a "features" list; an error response
    # has an "error" key — detect both and fail loudly.
    if "error" in state_geojson:
        err = state_geojson["error"]
        faasr_log(f"TIGERweb state boundary service returned an error: {err}")
        raise RuntimeError(f"TIGERweb state boundary API error: {err}")

    if not state_geojson.get("features"):
        faasr_log(
            "TIGERweb returned 0 features for California state boundary "
            f"(STUSAB='{CA_STUSAB}'). Check service availability and query."
        )
        raise RuntimeError(
            f"No California state boundary features returned from TIGERweb "
            f"({state_url}). Cannot proceed without real data."
        )

    faasr_log(
        f"State boundary: {len(state_geojson['features'])} feature(s) received"
    )

    # ------------------------------------------------------------------
    # 2. Fetch California county boundaries  (MapServer layer 1 = Counties)
    # ------------------------------------------------------------------
    faasr_log(
        "fetch_california_boundary: fetching California county boundaries "
        "from US Census Bureau TIGERweb"
    )

    county_url = f"{TIGERWEB_BASE}/1/query"
    county_params = {
        "where": f"STATE='{CA_STATE_FIPS}'",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
    }

    try:
        county_resp = requests.get(county_url, params=county_params, timeout=60)
    except requests.exceptions.RequestException as exc:
        faasr_log(f"Network error fetching California county boundaries: {exc}")
        raise RuntimeError(
            f"Failed to reach TIGERweb county boundaries service at "
            f"{county_url}: {exc}"
        ) from exc

    if county_resp.status_code != 200:
        faasr_log(
            f"TIGERweb county boundaries service returned HTTP "
            f"{county_resp.status_code}: {county_resp.text[:500]}"
        )
        raise RuntimeError(
            f"TIGERweb county boundaries request failed with HTTP "
            f"{county_resp.status_code}"
        )

    county_geojson = county_resp.json()

    if "error" in county_geojson:
        err = county_geojson["error"]
        faasr_log(f"TIGERweb county boundaries service returned an error: {err}")
        raise RuntimeError(f"TIGERweb county boundaries API error: {err}")

    if not county_geojson.get("features"):
        faasr_log(
            "TIGERweb returned 0 features for California county boundaries "
            f"(STATE='{CA_STATE_FIPS}'). Check service availability and query."
        )
        raise RuntimeError(
            f"No California county boundary features returned from TIGERweb "
            f"({county_url}). Cannot proceed without real data."
        )

    faasr_log(
        f"County boundaries: {len(county_geojson['features'])} feature(s) received"
    )

    # ------------------------------------------------------------------
    # 3. Write to temp files and upload both GeoJSON files to S3
    # ------------------------------------------------------------------
    tmp_state_path = None
    tmp_county_path = None

    try:
        # --- State boundary ---
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".geojson", delete=False
        ) as tmp_state:
            tmp_state_path = tmp_state.name
            json.dump(state_geojson, tmp_state)

        faasr_log(f"Uploading {output1} to folder '{folder}'")
        faasr_put_file(
            local_file=tmp_state_path,
            remote_folder=folder,
            remote_file=output1,
        )
        faasr_log(f"Successfully uploaded {output1} to S3 folder '{folder}'")

        # --- County boundaries ---
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".geojson", delete=False
        ) as tmp_county:
            tmp_county_path = tmp_county.name
            json.dump(county_geojson, tmp_county)

        faasr_log(f"Uploading {output2} to folder '{folder}'")
        faasr_put_file(
            local_file=tmp_county_path,
            remote_folder=folder,
            remote_file=output2,
        )
        faasr_log(f"Successfully uploaded {output2} to S3 folder '{folder}'")

    finally:
        if tmp_state_path and os.path.exists(tmp_state_path):
            os.remove(tmp_state_path)
        if tmp_county_path and os.path.exists(tmp_county_path):
            os.remove(tmp_county_path)

    faasr_log("fetch_california_boundary: complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---