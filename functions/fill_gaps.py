def fill_gaps(folder: str, input1: str, output1: str) -> None:
    """Forward-fill missing values in the S_cation and S_anion columns only.

    Propagates the last valid observation forward within each of those two
    columns; every other column and the row ordering is left untouched.
    """
    import pandas as pd

    fill_columns = ["S_cation", "S_anion"]

    faasr_log(f"fill_gaps: downloading converted influent '{input1}' from folder '{folder}'")
    local_in = "influent_converted.csv"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)
    faasr_log(f"fill_gaps: read {len(df)} rows, {len(df.columns)} columns")

    missing = [c for c in fill_columns if c not in df.columns]
    if missing:
        msg = f"fill_gaps: required columns missing from input CSV: {missing}"
        faasr_log(msg)
        raise ValueError(msg)

    for col in fill_columns:
        n_before = int(df[col].isna().sum())
        df[col] = df[col].ffill()
        n_after = int(df[col].isna().sum())
        faasr_log(f"fill_gaps: {col} forward-filled {n_before - n_after} missing values "
                  f"({n_after} still missing at series start)")

    local_out = "influent_gapfilled.csv"
    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"fill_gaps: wrote gap-filled influent '{output1}' to folder '{folder}'")
