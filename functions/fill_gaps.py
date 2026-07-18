def fill_gaps(folder: str, input1: str, output1: str) -> None:
    """Fourth step of the PyADM1 digester preprocessing pipeline.

    Reads the solubles-converted influent CSV (input1) from the S3 folder,
    forward-fills missing values in the S_cation and S_anion columns using
    pandas ffill (propagating the last valid observation forward), preserves all
    other columns unchanged, and writes the result to output1.
    """
    import pandas as pd

    local_in = "influent_solubles_converted.csv"
    local_out = "influent_gaps_filled.csv"

    faasr_log(f"fill_gaps: fetching '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    target_cols = ["S_cation", "S_anion"]
    missing = [c for c in target_cols if c not in df.columns]
    if missing:
        msg = (
            f"fill_gaps: expected column(s) {missing} not found in '{input1}'. "
            f"Columns present: {list(df.columns)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    for col in target_cols:
        n_missing = int(df[col].isna().sum())
        df[col] = df[col].ffill()
        faasr_log(f"fill_gaps: forward-filled {n_missing} missing value(s) in '{col}'")

    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"fill_gaps: wrote gap-filled influent to '{output1}'")
