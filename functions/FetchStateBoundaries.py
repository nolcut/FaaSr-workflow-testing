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
        local_file="earthquake_data.json",
        remote_file="earthquake_data.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-6/FetchEarthquakeData",
    )

    # --- Generated code ---


    faasr_log("Starting download of US Census Bureau state boundary shapefile")

    url = "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_state_20m.zip"

    try:
        faasr_log(f"Downloading shapefile from {url}")
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        faasr_log("Download complete, extracting zip archive")

        zip_bytes = io.BytesIO(response.content)
        extract_dir = "/tmp/census_states"
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_bytes) as zf:
            zf.extractall(extract_dir)
            faasr_log(f"Extracted files: {zf.namelist()}")

        shp_files = [f for f in os.listdir(extract_dir) if f.endswith(".shp")]
        if not shp_files:
            faasr_log("ERROR: No .shp file found in extracted archive")
            raise FileNotFoundError("No shapefile found in zip archive")

        shp_path = os.path.join(extract_dir, shp_files[0])
        faasr_log(f"Loading shapefile: {shp_path}")
        gdf = gpd.read_file(shp_path)
        faasr_log(f"Loaded GeoDataFrame with {len(gdf)} records and columns: {list(gdf.columns)}")

        western_states = ["California", "Oregon", "Washington", "Nevada", "Idaho", "Arizona", "Utah", "Montana"]
        faasr_log(f"Filtering to western states: {western_states}")

        gdf_western = gdf[gdf["NAME"].isin(western_states)].copy()
        faasr_log(f"Filtered GeoDataFrame contains {len(gdf_western)} states")

        found_states = sorted(gdf_western["NAME"].tolist())
        faasr_log(f"States found: {found_states}")

        if len(gdf_western) != len(western_states):
            missing = set(western_states) - set(gdf_western["NAME"].tolist())
            faasr_log(f"WARNING: Missing states: {missing}")

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "western_states.geojson")

        faasr_log(f"Saving filtered GeoDataFrame as GeoJSON to {output_path}")
        gdf_western.to_file(output_path, driver="GeoJSON")
        faasr_log(f"Successfully saved western states GeoJSON to {output_path}")

    except requests.exceptions.RequestException as e:
        faasr_log(f"ERROR downloading shapefile: {e}")
        raise
    except Exception as e:
        faasr_log(f"ERROR processing shapefile: {e}")
        raise
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="FetchStateBoundaries.py",
        remote_file="FetchStateBoundaries.py",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/FetchStateBoundaries",
    )
    faasr_put_file(
        local_file="western_states.geojson",
        remote_file="western_states.geojson",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/FetchStateBoundaries",
    )
