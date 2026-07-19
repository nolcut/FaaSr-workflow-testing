import pandas as pd
import numpy as np
import tempfile
import os

def interpolate(folder: str, input1: str, output1: str) -> None:
    faasr_log("interpolate: starting")

    with tempfile.TemporaryDirectory() as tmp:
        local_in = os.path.join(tmp, "in.csv")
        local_out = os.path.join(tmp, "out.csv")

        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
        df = pd.read_csv(local_in)
        faasr_log(f"interpolate: loaded {len(df)} rows, {len(df.columns)} columns")

        time_col = "time"
        operational_cols = ["Q", "T_ad", "S_cation", "S_anion"]
        # All columns except time and the four operational ones are weekly lab columns
        lab_cols = [c for c in df.columns if c != time_col and c not in operational_cols]
        faasr_log(f"interpolate: {len(lab_cols)} lab columns, 4 operational columns")

        # Use time as numeric index for index-based interpolation
        df = df.set_index(time_col)

        # Operational columns: forward-fill to cover any remaining NaN gaps
        for col in operational_cols:
            if col in df.columns:
                df[col] = df[col].ffill()

        # Lab columns: currently step-held (forward-filled from weekly measurement).
        # Recover the actual weekly sample points (first occurrence of each new run),
        # set the held-constant intermediate rows to NaN, then interpolate linearly
        # between sample points.  Forward-fill the tail to extend the last observation
        # to the end of the time span (no measurement yet received past the last sample).
        for col in lab_cols:
            series = df[col].copy()
            # Mark transition rows (first row of each new constant run); NaN shift → always True at row 0
            changes = series.ne(series.shift())
            # Keep only the sample-point values; blank out held rows
            samples = series.copy()
            samples[~changes] = np.nan
            # Linear interpolation between sample points (index = time in days)
            samples = samples.interpolate(method="index")
            # Forward-fill any trailing NaN after the last sample point
            samples = samples.ffill()
            df[col] = samples

        df = df.reset_index()
        faasr_log(f"interpolate: writing {len(df)} rows")
        df.to_csv(local_out, index=False)
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
        faasr_log("interpolate: done")
