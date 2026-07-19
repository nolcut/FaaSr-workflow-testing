import pandas as pd
import tempfile
import os

def convert_units(folder: str, input1: str, output1: str) -> None:
    faasr_log("convert_units: starting unit conversion")

    with tempfile.TemporaryDirectory() as tmp:
        local_in = os.path.join(tmp, "raw.csv")
        local_out = os.path.join(tmp, "converted.csv")

        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

        df = pd.read_csv(local_in)
        faasr_log(f"convert_units: loaded {len(df)} rows, columns: {list(df.columns)}")

        # Q: MGD -> m3/d
        if "Q" not in df.columns:
            raise ValueError("Expected column 'Q' not found in input")
        df["Q"] = df["Q"] * 3785.41

        # Temperature: Fahrenheit -> Celsius, rename column to T_ad
        temp_col = "T (F)"
        if temp_col not in df.columns:
            raise ValueError(f"Expected column '{temp_col}' not found in input")
        df["T_ad"] = (df[temp_col] - 32) * 5.0 / 9.0
        df = df.drop(columns=[temp_col])

        # COD fractions: divide by 1000
        # All S_* except the four explicitly excluded; all X_*
        excluded_s = {"S_IC", "S_IN", "S_cation", "S_anion"}
        for col in df.columns:
            if (col.startswith("S_") and col not in excluded_s) or col.startswith("X_"):
                df[col] = df[col] / 1000.0

        df.to_csv(local_out, index=False)
        faasr_log("convert_units: writing output")
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
        faasr_log("convert_units: done")
