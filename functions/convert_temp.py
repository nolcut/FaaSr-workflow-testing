def convert_temp(folder: str, input1: str, output1: str) -> None:
    """Second step of the PyADM1 digester preprocessing pipeline.

    Reads the flow-converted influent CSV (input1) from the S3 folder, converts
    the temperature column from Fahrenheit to Celsius using (F-32)*5/9, renames
    the column to 'T (C)', and writes the updated dataframe back to output1.
    """
    import pandas as pd

    local_in = "influent_flow_converted.csv"
    local_out = "influent_temp_converted.csv"

    faasr_log(f"convert_temp: fetching '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    if "T (F)" not in df.columns:
        msg = (
            f"convert_temp: expected temperature column 'T (F)' not found in "
            f"'{input1}'. Columns present: {list(df.columns)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Convert Fahrenheit -> Celsius and rename the column to 'T (C)'.
    df["T (F)"] = (pd.to_numeric(df["T (F)"], errors="raise") - 32) * 5 / 9
    df = df.rename(columns={"T (F)": "T (C)"})
    faasr_log(f"convert_temp: converted {len(df)} temperature values F -> C")

    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"convert_temp: wrote temperature-converted influent to '{output1}'")
