import os


def FetchStateBoundaries():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)

    # Download inputs
    faasr_get_file(
        local_file="earthquake_data_raw.json",
        remote_file="earthquake_data_raw.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="date_metadata.json",
        remote_file="date_metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="FetchEarthquakeData.py",
        remote_file="FetchEarthquakeData.py",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-3/FetchEarthquakeData",
    )

    # --- Generated code ---
    import os
    import requests
    import zipfile
    import io

    faasr_install("geopandas")
    import geopandas as gpd

    faasr_log("Starting download of US Census Bureau state boundary shapefile")

    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    url = "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_20m.zip"

    faasr_log(f"Downloading shapefile from {url}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    faasr_log("Download complete, extracting zip archive")

    zip_bytes = io.BytesIO(response.content)
    extract_dir = "/tmp/agent/census_shp"
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_bytes) as zf:
        zf.extractall(extract_dir)
        faasr_log(f"Extracted files: {zf.namelist()}")

    shp_files = [f for f in os.listdir(extract_dir) if f.endswith(".shp")]
    if not shp_files:
        faasr_log("ERROR: No .shp file found in extracted archive")
        raise FileNotFoundError("No shapefile found in extracted archive")

    shp_path = os.path.join(extract_dir, shp_files[0])
    faasr_log(f"Loading shapefile: {shp_path}")
    gdf = gpd.read_file(shp_path)

    faasr_log(f"Loaded GeoDataFrame with {len(gdf)} states/territories")
    faasr_log(f"Columns: {list(gdf.columns)}")

    western_states = [
        "California", "Oregon", "Washington", "Nevada",
        "Idaho", "Arizona", "Utah", "Montana"
    ]

    name_col = None
    for col in ["NAME", "Name", "name", "STATE_NAME"]:
        if col in gdf.columns:
            name_col = col
            break

    if name_col is None:
        faasr_log(f"ERROR: Could not find name column. Available columns: {list(gdf.columns)}")
        raise ValueError("Could not identify state name column in shapefile")

    faasr_log(f"Using column '{name_col}' to filter states")
    gdf_western = gdf[gdf[name_col].isin(western_states)].copy()
    faasr_log(f"Filtered to {len(gdf_western)} western states: {sorted(gdf_western[name_col].tolist())}")

    output_path = os.path.join(output_dir, "western_states.geojson")
    gdf_western = gdf_western.to_crs(epsg=4326)
    gdf_western.to_file(output_path, driver="GeoJSON")
    faasr_log(f"Saved filtered western states GeoDataFrame to {output_path}")

    import json
    summary = {
        "states_included": sorted(gdf_western[name_col].tolist()),
        "num_states": len(gdf_western),
        "crs": "EPSG:4326",
        "output_file": "western_states.geojson"
    }
    summary_path = os.path.join(output_dir, "western_states_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    faasr_log(f"Saved summary metadata to {summary_path}")
    faasr_log("FetchStateBoundaries step complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="FetchStateBoundaries.py",
        remote_file="FetchStateBoundaries.py",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/FetchStateBoundaries",
    )
    faasr_put_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/FetchStateBoundaries",
    )
    faasr_put_file(
        local_file="western_states_summary.json",
        remote_file="western_states_summary.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-3/FetchStateBoundaries",
    )
