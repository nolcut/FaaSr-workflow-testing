import json
import os
import tempfile

import numpy as np
import pandas as pd


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "random_numbers.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file random_numbers.csv must exist in S3 before calculate_statistics can run")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "statistics.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output file statistics.json must exist in S3 after calculate_statistics completes")
        raise SystemExit(1)
# --- end contract helpers ---


def calculate_statistics(folder: str, input1: str, output1: str) -> None:
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("Starting calculate_statistics")

    # Download the CSV of random numbers from S3
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp_in:
        tmp_in_path = tmp_in.name

    tmp_out_path = None
    try:
        faasr_get_file(local_file=tmp_in_path, remote_folder=folder, remote_file=input1)
        faasr_log(f"Downloaded {input1} from folder {folder}")

        # Read the CSV — one column named 'value', 100 rows
        df = pd.read_csv(tmp_in_path)
        if "value" not in df.columns:
            msg = f"Expected column 'value' in {input1}, got columns: {list(df.columns)}"
            faasr_log(msg)
            raise ValueError(msg)

        values = df["value"].to_numpy(dtype=float)
        faasr_log(f"Loaded {len(values)} values from {input1}")

        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1))   # sample std deviation (ddof=1)

        faasr_log(f"Computed mean={mean:.6f}, std={std:.6f}")

        stats = {"mean": mean, "std": std}

        # Write JSON to a temp file and upload
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as tmp_out:
            tmp_out_path = tmp_out.name
            json.dump(stats, tmp_out, indent=2)

        faasr_put_file(local_file=tmp_out_path, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded {output1} to folder {folder}")

    finally:
        if os.path.exists(tmp_in_path):
            os.remove(tmp_in_path)
        if tmp_out_path and os.path.exists(tmp_out_path):
            os.remove(tmp_out_path)

    faasr_log("calculate_statistics complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---