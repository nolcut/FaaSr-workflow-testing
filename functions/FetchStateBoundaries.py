import os
import requests
import zipfile
import io
import geopandas as gpd


def FetchStateBoundaries():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # Download inputs
    faasr_get_file(
        local_file="earthquakes.geojson",
        remote_file="earthquakes.geojson",
        local_folder="/tmp/agent/input",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/FetchEarthquakeData",
    )
    faasr_get_file(
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/FetchEarthquakeData",
    )

    # --- Generated code ---


    faasr_log("Starting download of US Census Bureau state boundary shapefiles")

    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    url = "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_20m.zip"
    faasr_log(f"Downloading state boundaries from: {url}")

    response = requests.get(url, timeout=60)
    if response.status_code != 200:
        faasr_log(f"ERROR: Failed to download file. HTTP status code: {response.status_code}")
        raise RuntimeError(f"Failed to download shapefile: HTTP {response.status_code}")

    faasr_log("Download successful. Unzipping archive...")

    zip_extract_dir = "/tmp/agent/state_shp"
    os.makedirs(zip_extract_dir, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        zf.extractall(zip_extract_dir)
        faasr_log(f"Extracted files: {zf.namelist()}")

    shp_files = [f for f in os.listdir(zip_extract_dir) if f.endswith(".shp")]
    if not shp_files:
        faasr_log("ERROR: No .shp file found in the extracted archive.")
        raise FileNotFoundError("No shapefile found after extraction.")

    shp_path = os.path.join(zip_extract_dir, shp_files[0])
    faasr_log(f"Loading shapefile: {shp_path}")

    gdf = gpd.read_file(shp_path)
    faasr_log(f"Loaded GeoDataFrame with {len(gdf)} rows and columns: {list(gdf.columns)}")

    western_states = ["California", "Oregon", "Washington", "Nevada", "Idaho", "Arizona", "Utah", "Montana"]
    faasr_log(f"Filtering to retain states: {western_states}")

    filtered_gdf = gdf[gdf["NAME"].isin(western_states)][["geometry", "NAME"]].copy()
    filtered_gdf = filtered_gdf.reset_index(drop=True)

    faasr_log(f"Filtered GeoDataFrame has {len(filtered_gdf)} rows.")
    faasr_log(f"States retained: {sorted(filtered_gdf['NAME'].tolist())}")

    if filtered_gdf.crs is None:
        faasr_log("WARNING: CRS is None, setting to EPSG:4326")
        filtered_gdf = filtered_gdf.set_crs("EPSG:4326")
    elif filtered_gdf.crs.to_epsg() != 4326:
        faasr_log(f"Reprojecting from {filtered_gdf.crs} to EPSG:4326")
        filtered_gdf = filtered_gdf.to_crs("EPSG:4326")

    output_path = os.path.join(output_dir, "western_states.geojson")
    filtered_gdf.to_file(output_path, driver="GeoJSON")
    faasr_log(f"Saved filtered state boundaries to: {output_path}")

    faasr_log("State boundary processing complete.")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-11/{faasr_invocation_id()}/FetchStateBoundaries",
    )
