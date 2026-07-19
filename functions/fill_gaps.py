import pandas as pd
import tempfile
import os

def fill_gaps(folder: str, input1: str, output1: str) -> None:
    faasr_log("fill_gaps: starting gap fill")

    with tempfile.TemporaryDirectory() as tmp:
        local_in = os.path.join(tmp, "in.csv")
        local_out = os.path.join(tmp, "out.csv")

        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

        df = pd.read_csv(local_in)
        faasr_log(f"fill_gaps: loaded {len(df)} rows")

        for col in ("S_cation", "S_anion"):
            if col not in df.columns:
                raise ValueError(f"Expected column '{col}' not found in input")
            before = df[col].isna().sum()
            df[col] = df[col].ffill()
            after = df[col].isna().sum()
            faasr_log(f"fill_gaps: {col} NaN before={before} after={after}")

        df.to_csv(local_out, index=False)
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
        faasr_log("fill_gaps: done")
