import json
import os
import shutil
from PIL import Image


def UploadMapToS3():
    os.makedirs("/tmp/agent/input", exist_ok=True)
    os.makedirs("/tmp/agent/output", exist_ok=True)
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    # Download inputs
    faasr_get_file(
        local_file="western_us_earthquake_map.png",
        remote_file="western_us_earthquake_map.png",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-6/RenderEarthquakeMap",
    )
    faasr_get_file(
        local_file="_manifest.json",
        remote_file="_manifest.json",
        local_folder="/tmp/agent/input",
        remote_folder="Western-US-Earthquake-Map-6/RenderEarthquakeMap",
    )

    # --- Generated code ---

    # Define directories
    input_dir = "/tmp/agent/input"
    output_dir = "/tmp/agent/output"

    os.makedirs(output_dir, exist_ok=True)

    faasr_log("Starting PNG image verification and upload task.")

    # Locate the PNG image file
    png_filename = "western_us_earthquake_map.png"
    png_input_path = os.path.join(input_dir, png_filename)

    faasr_log(f"Looking for PNG file at: {png_input_path}")

    # Verify the file exists
    if not os.path.exists(png_input_path):
        faasr_log(f"ERROR: PNG file not found at {png_input_path}")
        raise FileNotFoundError(f"PNG file not found: {png_input_path}")

    faasr_log(f"PNG file found: {png_input_path}")

    # Verify it is a valid PNG image
    try:
        with Image.open(png_input_path) as img:
            img.verify()
        faasr_log(f"PNG file verified as a valid image.")
        # Re-open to get metadata (verify() closes the file)
        with Image.open(png_input_path) as img:
            width, height = img.size
            mode = img.mode
            fmt = img.format
        faasr_log(f"Image details - Format: {fmt}, Size: {width}x{height}, Mode: {mode}")
    except Exception as e:
        faasr_log(f"ERROR: File is not a valid PNG image: {e}")
        raise ValueError(f"Invalid PNG image: {e}")

    # Get file size
    file_size = os.path.getsize(png_input_path)
    faasr_log(f"PNG file size: {file_size} bytes ({file_size / 1024:.1f} KB)")

    # Copy the PNG to the output directory so the eval agent uploads it to S3
    png_output_path = os.path.join(output_dir, png_filename)
    shutil.copy2(png_input_path, png_output_path)
    faasr_log(f"PNG file copied to output directory: {png_output_path}")

    # Verify the copy succeeded
    if not os.path.exists(png_output_path):
        faasr_log("ERROR: Failed to copy PNG to output directory.")
        raise RuntimeError("Output PNG file not found after copy.")

    copied_size = os.path.getsize(png_output_path)
    if copied_size != file_size:
        faasr_log(f"ERROR: File size mismatch after copy. Original: {file_size}, Copied: {copied_size}")
        raise RuntimeError("File size mismatch after copy.")

    faasr_log(f"PNG file successfully staged for S3 upload. Output size: {copied_size} bytes.")

    # Write a confirmation JSON result
    result = {
        "status": "success",
        "file": png_filename,
        "format": fmt,
        "width": width,
        "height": height,
        "mode": mode,
        "file_size_bytes": file_size,
        "output_path": png_output_path,
        "message": "PNG image verified and staged for durable S3 storage as final workflow output."
    }

    result_path = os.path.join(output_dir, "upload_confirmation.json")
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    faasr_log(f"Upload confirmation written to: {result_path}")
    faasr_log("Task complete: western_us_earthquake_map.png has been verified and uploaded as the final workflow output.")

    print(json.dumps(result, indent=2))
    # --- End generated code ---

    # Upload outputs
    faasr_put_file(
        local_file="UploadMapToS3.py",
        remote_file="UploadMapToS3.py",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/UploadMapToS3",
    )
    faasr_put_file(
        local_file="western_us_earthquake_map.png",
        remote_file="western_us_earthquake_map.png",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/UploadMapToS3",
    )
    faasr_put_file(
        local_file="upload_confirmation.json",
        remote_file="upload_confirmation.json",
        local_folder="/tmp/agent/output",
        remote_folder="Western-US-Earthquake-Map-6/UploadMapToS3",
    )
