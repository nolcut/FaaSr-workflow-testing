def convert_flow(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    local_in = "digester_influent_raw.csv"
    local_out = "influent_flow_converted.csv"

    faasr_log(f"convert_flow: fetching {input1} from folder {folder}")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    if "Q" not in df.columns:
        msg = f"convert_flow: required column 'Q' not found in {input1}; columns present: {list(df.columns)}"
        faasr_log(msg)
        raise ValueError(msg)

    # Convert flow Q from MGD to m3/d
    df["Q"] = df["Q"] * 3785.411784
    faasr_log("convert_flow: converted Q from MGD to m3/d (x3785.411784)")

    df.to_csv(local_out, index=False)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"convert_flow: wrote {output1} to folder {folder}")
