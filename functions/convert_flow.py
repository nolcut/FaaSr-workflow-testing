def convert_flow(folder: str, input1: str, input2: str, output1: str, output2: str) -> None:
    """First step of the PyADM1 digester preprocessing pipeline.

    Reads the raw influent time-series CSV (input1) and the initial-conditions
    CSV (input2) from the S3 folder. Converts the flow column Q from MGD to
    m3/d by multiplying by the exact factor 3785.411784, writes the
    flow-converted influent data to output1, and passes the initial-conditions
    CSV through unchanged as output2.
    """
    import pandas as pd

    MGD_TO_M3_PER_DAY = 3785.411784

    local_influent = "influent_raw.csv"
    local_initial = "digester_initial.csv"
    local_converted = "influent_flow_converted.csv"

    # --- Fetch inputs from S3 ---
    faasr_log(f"convert_flow: fetching raw influent '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_influent, remote_folder=folder, remote_file=input1)

    faasr_log(f"convert_flow: fetching initial conditions '{input2}' from folder '{folder}'")
    faasr_get_file(local_file=local_initial, remote_folder=folder, remote_file=input2)

    # --- Load influent data ---
    influent = pd.read_csv(local_influent)

    if "Q" not in influent.columns:
        msg = (
            f"convert_flow: expected flow column 'Q' not found in '{input1}'. "
            f"Columns present: {list(influent.columns)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # --- Convert flow Q: MGD -> m3/d ---
    influent["Q"] = pd.to_numeric(influent["Q"], errors="raise") * MGD_TO_M3_PER_DAY
    faasr_log(
        f"convert_flow: converted {len(influent)} Q values from MGD to m3/d "
        f"(factor {MGD_TO_M3_PER_DAY})"
    )

    # --- Write flow-converted influent data ---
    influent.to_csv(local_converted, index=False)
    faasr_put_file(local_file=local_converted, remote_folder=folder, remote_file=output1)
    faasr_log(f"convert_flow: wrote flow-converted influent to '{output1}'")

    # --- Pass initial conditions through unchanged ---
    faasr_put_file(local_file=local_initial, remote_folder=folder, remote_file=output2)
    faasr_log(f"convert_flow: passed initial conditions through unchanged as '{output2}'")
