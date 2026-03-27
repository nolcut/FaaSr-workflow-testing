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
        local_file="metadata.json",
        remote_file="metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-8/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="earthquakes_clean.geojson",
        remote_file="earthquakes_clean.geojson",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-8/ProcessEarthquakeData",
    )

    # --- Generated code ---


    faasr_log("Starting download of US Census Bureau state boundary shapefiles")

    output_dir = "/tmp/agent/output"
    os.makedirs(output_dir, exist_ok=True)

    # Download the shapefile zip archive
    url = "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_20m.zip"
    faasr_log(f"Downloading state boundaries from: {url}")

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    faasr_log(f"Download complete, size: {len(response.content)} bytes")

    # Extract the zip archive in memory
    faasr_log("Extracting shapefile archive")
    extract_dir = "/tmp/agent/census_shp"
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        zf.extractall(extract_dir)
        extracted_files = zf.namelist()
        faasr_log(f"Extracted files: {extracted_files}")

    # Find the .shp file
    shp_file = None
    for f in os.listdir(extract_dir):
        if f.endswith(".shp"):
            shp_file = os.path.join(extract_dir, f)
            break

    if shp_file is None:
        faasr_log("ERROR: No .shp file found in extracted archive")
        raise FileNotFoundError("No .shp file found in extracted archive")

    faasr_log(f"Reading shapefile: {shp_file}")
    gdf = gpd.read_file(shp_file)
    faasr_log(f"Loaded GeoDataFrame with {len(gdf)} features, columns: {list(gdf.columns)}")

    # Filter to the eight western states
    western_states = [
        "California", "Oregon", "Washington", "Nevada",
        "Idaho", "Arizona", "Utah", "Montana"
    ]

    faasr_log(f"Filtering to western states: {western_states}")
    gdf_western = gdf[gdf["NAME"].isin(western_states)].copy()
    faasr_log(f"Filtered GeoDataFrame has {len(gdf_western)} features")

    # Ensure CRS is WGS84 (EPSG:4326) for GeoJSON
    if gdf_western.crs is None or gdf_western.crs.to_epsg() != 4326:
        faasr_log("Reprojecting to EPSG:4326 (WGS84)")
        gdf_western = gdf_western.to_crs(epsg=4326)

    # Save as GeoJSON
    output_path = os.path.join(output_dir, "western_states.geojson")
    gdf_western.to_file(output_path, driver="GeoJSON")
    faasr_log(f"Saved western states GeoJSON to: {output_path}")

    # Verify the output
    gdf_check = gpd.read_file(output_path)
    faasr_log(f"Verification: output GeoJSON has {len(gdf_check)} features")
    faasr_log(f"States included: {sorted(gdf_check['NAME'].tolist())}")

    faasr_log("State boundary download and filtering complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-8/2026-03-26-19-59-26/outputs",
    )
