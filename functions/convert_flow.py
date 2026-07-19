def convert_flow(folder: str, input1: str, input2: str, output1: str) -> None:
    """Convert digester influent flow rate Q from MGD to m3/d.

    Reads the raw influent time-series CSV (input1) and the initial-conditions
    CSV (input2) from the S3 folder. Multiplies every value of the flow column
    Q by 3785.411784 (MGD -> m3/d), leaving all other columns untouched, and
    writes the result to output1. The initial-conditions CSV is passed through
    unchanged (downstream functions read it directly from S3).
    """
    import os
    import pandas as pd

    MGD_TO_M3D = 3785.411784

    local_influent = "influent_raw.csv"
    local_initial = "initial.csv"
    local_out = "influent_converted.csv"

    faasr_log(f"convert_flow: fetching {input1} and {input2} from folder '{folder}'")
    faasr_get_file(local_file=local_influent, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_initial, remote_folder=folder, remote_file=input2)

    df = pd.read_csv(local_influent)

    if "Q" not in df.columns:
        msg = (f"convert_flow: expected flow column 'Q' not found in {input1}; "
               f"columns are {list(df.columns)}")
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"convert_flow: converting Q (MGD -> m3/d) over {len(df)} rows "
              f"by factor {MGD_TO_M3D}")
    df["Q"] = df["Q"] * MGD_TO_M3D

    df.to_csv(local_out, index=False)

    faasr_log(f"convert_flow: writing converted influent to {output1}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    for f in (local_influent, local_initial, local_out):
        if os.path.exists(f):
            os.remove(f)

    faasr_log("convert_flow: complete")
