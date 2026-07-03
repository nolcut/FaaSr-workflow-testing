import numpy as np
import pandas as pd
import tempfile
import os


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "random_numbers.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file random_numbers.csv was not found in S3 after generation and upload")
        raise SystemExit(1)
# --- end contract helpers ---


def generate_random_numbers(folder: str, output1: str) -> None:
    faasr_log("Generating 100 random numbers from a standard normal distribution")

    # Generate 100 random numbers from a standard normal distribution
    rng = np.random.default_rng()
    numbers = rng.standard_normal(100)

    # Build a DataFrame with one value per row
    df = pd.DataFrame(numbers, columns=["value"])

    # Write to a local temp file then upload
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
        tmp_path = tmp.name

    try:
        df.to_csv(tmp_path, index=False)
        faasr_log(f"Generated {len(df)} random numbers; uploading as {output1}")
        faasr_put_file(local_file=tmp_path, remote_folder=folder, remote_file=output1)
        faasr_log(f"Successfully uploaded {output1} to folder {folder}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---