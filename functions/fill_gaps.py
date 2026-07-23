"""FaaSr step 2: fill-gaps.

Forward-fill missing S_cation and S_anion values. These two ionic-strength
columns come from an intermittent titration measurement, so gaps are carried
forward from the last known reading. A trailing back-fill is applied only to
cover any leading NaNs at the very start of the series (nothing to carry
forward from yet).
"""

try:
    from FaaSr_py.client.py_client_stubs import faasr_get_file, faasr_put_file, faasr_log
except Exception:  # pragma: no cover
    pass

import pandas as pd

FILL_COLUMNS = ["S_cation", "S_anion"]


def fill_gaps(folder, input_file="influent_units_converted.csv",
              output_file="influent_filled.csv"):
    faasr_log(f"fill_gaps: downloading {folder}/{input_file}")
    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file="in.csv")

    df = pd.read_csv("in.csv")

    for col in FILL_COLUMNS:
        if col not in df.columns:
            faasr_log(f"fill_gaps: WARNING - column '{col}' not found; skipping")
            continue
        n_missing = int(df[col].isna().sum())
        # Forward-fill; back-fill only handles leading NaNs.
        df[col] = df[col].ffill().bfill()
        faasr_log(f"fill_gaps: forward-filled {n_missing} missing values in '{col}'")

    df.to_csv(output_file, index=False)
    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"fill_gaps: wrote {folder}/{output_file}")
