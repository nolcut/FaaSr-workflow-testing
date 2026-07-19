def convert_solubles(folder: str, input1: str, output1: str) -> None:
    """Convert soluble species concentrations from mg/L to kg/m3.

    Reads the influent CSV (input1) from the S3 folder, identifies the soluble
    species columns (those prefixed with 'S_'), divides each such column's
    values by 1000 (mg/L -> kg/m3), leaves all non-soluble columns (flow 'Q',
    temperature 'T (C)', particulate 'X_*', 'time') unchanged, and writes the
    result back to output1 (chained cleaning pipeline).
    """
    import os
    import pandas as pd

    local_in = "influent_in.csv"
    local_out = "influent_out.csv"

    faasr_log(f"convert_solubles: fetching {input1} from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    soluble_cols = [c for c in df.columns if c.startswith("S_")]
    if not soluble_cols:
        msg = (f"convert_solubles: no soluble columns (prefix 'S_') found in "
               f"{input1}; columns are {list(df.columns)}")
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"convert_solubles: converting {len(soluble_cols)} soluble columns "
              f"(mg/L -> kg/m3) over {len(df)} rows: {soluble_cols}")
    for c in soluble_cols:
        df[c] = df[c] / 1000.0

    df.to_csv(local_out, index=False)

    faasr_log(f"convert_solubles: writing converted influent to {output1}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    for f in (local_in, local_out):
        if os.path.exists(f):
            os.remove(f)

    faasr_log("convert_solubles: complete")
