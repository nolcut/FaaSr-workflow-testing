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
        local_file="earthquakes_cleaned.csv",
        remote_file="earthquakes_cleaned.csv",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-7/ProcessEarthquakeData",
    )
    faasr_get_file(
        local_file="query_metadata.json",
        remote_file="query_metadata.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-7/FetchEarthquakeData",
    )

    # --- Generated code ---


    faasr_log("Starting download of US Census Bureau state boundary shapefile")

    url = "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_20m.zip"

    try:
        faasr_log(f"Downloading shapefile from {url}")
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        faasr_log(f"Download complete, size: {len(response.content)} bytes")
    except Exception as e:
        faasr_log(f"Error downloading shapefile: {e}")
        raise

    extract_dir = "/tmp/census_shapefile"
    os.makedirs(extract_dir, exist_ok=True)

    try:
        faasr_log("Extracting zip archive")
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            zf.extractall(extract_dir)
        faasr_log("Extraction complete")
    except Exception as e:
        faasr_log(f"Error extracting zip: {e}")
        raise

    shp_files = [f for f in os.listdir(extract_dir) if f.endswith(".shp")]
    if not shp_files:
        faasr_log("No .shp file found in extracted archive")
        raise FileNotFoundError("No shapefile found in extracted archive")

    shp_path = os.path.join(extract_dir, shp_files[0])
    faasr_log(f"Loading shapefile: {shp_path}")

    try:
        gdf = gpd.read_file(shp_path)
        faasr_log(f"Shapefile loaded with {len(gdf)} records and columns: {list(gdf.columns)}")
    except Exception as e:
        faasr_log(f"Error loading shapefile: {e}")
        raise

    western_states = ["California", "Oregon", "Washington", "Nevada", "Idaho", "Arizona", "Utah", "Montana"]

    faasr_log(f"Filtering to {len(western_states)} western states")
    filtered_gdf = gdf[gdf["NAME"].isin(western_states)][["NAME", "geometry"]].copy()
    filtered_gdf = filtered_gdf.reset_index(drop=True)
    faasr_log(f"Filtered GeoDataFrame has {len(filtered_gdf)} records")
    faasr_log(f"States included: {sorted(filtered_gdf['NAME'].tolist())}")

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "western_states.geojson")

    try:
        filtered_gdf.to_file(output_path, driver="GeoJSON")
        faasr_log(f"GeoJSON saved to {output_path}")
    except Exception as e:
        faasr_log(f"Error saving GeoJSON: {e}")
        raise

    faasr_log("Western states boundary GeoJSON creation complete")
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-7/FetchStateBoundaries",
    )
