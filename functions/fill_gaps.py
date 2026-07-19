def fill_gaps(folder: str, input1: str, output1: str) -> None:
    """Forward-fill missing S_cation and S_anion values in the influent data.

    Reads the influent CSV (input1) from the S3 folder, forward-fills (ffill)
    missing values in the 'S_cation' and 'S_anion' columns so each gap takes
    the last observed valid value, leaves all other columns unchanged, and
    writes the result back to output1 (chained cleaning pipeline).
    """
    import os
    import pandas as pd

    local_in = "influent_in.csv"
    local_out = "influent_out.csv"

    faasr_log(f"fill_gaps: fetching {input1} from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    target_cols = ["S_cation", "S_anion"]
    missing = [c for c in target_cols if c not in df.columns]
    if missing:
        msg = (f"fill_gaps: expected column(s) {missing} not found in {input1}; "
               f"columns are {list(df.columns)}")
        faasr_log(msg)
        raise ValueError(msg)

    na_before = {c: int(df[c].isna().sum()) for c in target_cols}
    faasr_log(f"fill_gaps: forward-filling {target_cols} over {len(df)} rows; "
              f"NaNs before: {na_before}")
    df[target_cols] = df[target_cols].ffill()
    na_after = {c: int(df[c].isna().sum()) for c in target_cols}
    faasr_log(f"fill_gaps: NaNs after ffill: {na_after}")

    df.to_csv(local_out, index=False)

    faasr_log(f"fill_gaps: writing filled influent to {output1}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    for f in (local_in, local_out):
        if os.path.exists(f):
            os.remove(f)

    faasr_log("fill_gaps: complete")
