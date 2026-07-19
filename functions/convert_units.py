def convert_units(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import tempfile, os

    local_in = tempfile.mktemp(suffix=".csv")
    local_out = tempfile.mktemp(suffix=".csv")

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"convert_units: read {input1} from {folder}")

    df = pd.read_csv(local_in)

    # Q: MGD -> m3/d
    df["Q"] = df["Q"] * 3785.41

    # T: Fahrenheit -> Celsius
    df["T (F)"] = (df["T (F)"] - 32) * 5 / 9

    # S_* columns (except excluded): mg/L -> kg COD/m3 (divide by 1000)
    exclude = {"S_IC", "S_IN", "S_cation", "S_anion"}
    s_cols = [c for c in df.columns if c.startswith("S_") and c not in exclude]
    df[s_cols] = df[s_cols] / 1000

    df.to_csv(local_out, index=False)
    faasr_log(f"convert_units: writing {output1} to {folder}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    os.remove(local_in)
    os.remove(local_out)
    faasr_log("convert_units: done")
