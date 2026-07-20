import pandas as pd


def fill_gaps(folder: str, input1: str, output1: str) -> None:
    local_in = "influent_converted.csv"
    local_out = "influent_filled.csv"

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"fill_gaps: read {input1}")

    df = pd.read_csv(local_in)

    for col in ("S_cation", "S_anion"):
        if col not in df.columns:
            faasr_log(f"fill_gaps: ERROR — column {col} not found")
            raise ValueError(f"Column {col} not found in input")
        before = df[col].isna().sum()
        df[col] = df[col].ffill()
        after = df[col].isna().sum()
        faasr_log(f"fill_gaps: {col} — filled {before - after} gaps ({after} remaining NaN)")

    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"fill_gaps: wrote {output1}")
