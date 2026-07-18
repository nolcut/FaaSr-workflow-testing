def convert_solubles(folder: str, input1: str, output1: str) -> None:
    """Third step of the PyADM1 digester preprocessing pipeline.

    Reads the temperature-converted influent CSV (input1) from the S3 folder,
    converts all soluble concentration columns from mg/L to kg/m3 by dividing
    their values by 1000, preserves all other columns unchanged, and writes the
    result to output1.

    In ADM1 nomenclature the soluble species are the state variables whose names
    begin with 'S_' (as opposed to the particulate 'X_' variables, and the
    non-concentration 'time', 'Q', and 'T (C)' columns).
    """
    import pandas as pd

    local_in = "influent_temp_converted.csv"
    local_out = "influent_solubles_converted.csv"

    faasr_log(f"convert_solubles: fetching '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    soluble_cols = [c for c in df.columns if c.startswith("S_")]
    if not soluble_cols:
        msg = (
            f"convert_solubles: no soluble concentration columns (prefix 'S_') "
            f"found in '{input1}'. Columns present: {list(df.columns)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Convert mg/L -> kg/m3 (1 mg/L = 0.001 kg/m3).
    for col in soluble_cols:
        df[col] = pd.to_numeric(df[col], errors="raise") / 1000

    faasr_log(
        f"convert_solubles: converted {len(soluble_cols)} soluble columns "
        f"mg/L -> kg/m3: {soluble_cols}"
    )

    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"convert_solubles: wrote solubles-converted influent to '{output1}'")
