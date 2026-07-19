def convert_temp(folder: str, input1: str, output1: str) -> None:
    """Convert digester influent temperature from Fahrenheit to Celsius.

    Reads the influent CSV (input1) from the S3 folder, converts the
    temperature column 'T (F)' with (F-32)*5/9, renames it to 'T (C)',
    leaves all other columns unchanged, and writes the result back to
    output1 (same influent file, chained cleaning pipeline).
    """
    import os
    import pandas as pd

    local_in = "influent_in.csv"
    local_out = "influent_out.csv"

    faasr_log(f"convert_temp: fetching {input1} from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    if "T (F)" not in df.columns:
        msg = (f"convert_temp: expected temperature column 'T (F)' not found in "
               f"{input1}; columns are {list(df.columns)}")
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"convert_temp: converting T (F) -> T (C) over {len(df)} rows")
    df["T (F)"] = (df["T (F)"] - 32) * 5.0 / 9.0
    df = df.rename(columns={"T (F)": "T (C)"})

    df.to_csv(local_out, index=False)

    faasr_log(f"convert_temp: writing converted influent to {output1}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    for f in (local_in, local_out):
        if os.path.exists(f):
            os.remove(f)

    faasr_log("convert_temp: complete")
