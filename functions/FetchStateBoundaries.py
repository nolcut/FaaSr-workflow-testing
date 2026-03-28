import os
import zipfile
import requests
import tempfile
import geopandas as gpd


def FetchStateBoundaries():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # --- Generated code ---


    faasr_log("Starting download of US Census Bureau state boundary shapefiles")

    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    url = "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_20m.zip"
    zip_path = os.path.join(tempfile.gettempdir(), "cb_2018_us_state_20m.zip")
    extract_dir = os.path.join(tempfile.gettempdir(), "cb_2018_us_state_20m")

    faasr_log(f"Downloading shapefile ZIP from {url}")
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    with open(zip_path, "wb") as f:
        f.write(response.content)

    faasr_log(f"Downloaded ZIP archive ({len(response.content)} bytes), extracting...")

    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    faasr_log("Extraction complete, loading shapefile with geopandas")

    shp_files = [f for f in os.listdir(extract_dir) if f.endswith(".shp")]
    if not shp_files:
        raise FileNotFoundError("No .shp file found in extracted archive")

    shp_path = os.path.join(extract_dir, shp_files[0])
    faasr_log(f"Loading shapefile: {shp_path}")

    gdf = gpd.read_file(shp_path)
    faasr_log(f"Loaded GeoDataFrame with {len(gdf)} rows and columns: {list(gdf.columns)}")

    western_states = [
        "California", "Oregon", "Washington", "Nevada",
        "Idaho", "Arizona", "Utah", "Montana"
    ]

    filtered_gdf = gdf[gdf["NAME"].isin(western_states)].copy()
    faasr_log(f"Filtered to {len(filtered_gdf)} western US states: {sorted(filtered_gdf['NAME'].tolist())}")

    if len(filtered_gdf) != len(western_states):
        missing = set(western_states) - set(filtered_gdf["NAME"].tolist())
        faasr_log(f"WARNING: Missing states in data: {missing}")

    output_path = os.path.join(output_dir, "western_states.geojson")
    filtered_gdf.to_file(output_path, driver="GeoJSON")
    faasr_log(f"Saved filtered GeoDataFrame to {output_path}")

    faasr_log("Done: western US state boundaries saved as GeoJSON")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/output",
        remote_folder=f"Western-US-Earthquake-Map-13-static/{faasr_invocation_id()}/FetchStateBoundaries",
    )
