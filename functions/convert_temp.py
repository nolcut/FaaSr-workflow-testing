def convert_temp(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    local_in = "influent_flow_converted.csv"
    local_out = "influent_temp_converted.csv"

    faasr_log(f"convert_temp: fetching {input1} from folder {folder}")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    if "T (F)" not in df.columns:
        msg = f"convert_temp: required column 'T (F)' not found in {input1}; columns present: {list(df.columns)}"
        faasr_log(msg)
        raise ValueError(msg)

    # Convert temperature from Fahrenheit to Celsius and rename the column
    df["T (F)"] = (df["T (F)"] - 32) * 5 / 9
    df = df.rename(columns={"T (F)": "T (C)"})
    faasr_log("convert_temp: converted T from F to C ((F-32)*5/9) and renamed column to 'T (C)'")

    df.to_csv(local_out, index=False)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"convert_temp: wrote {output1} to folder {folder}")
