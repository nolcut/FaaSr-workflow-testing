def convert_solubles(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    local_in = "influent_temp_converted.csv"
    local_out = "influent_solubles_converted.csv"

    faasr_log(f"convert_solubles: fetching {input1} from folder {folder}")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    # Non-concentration columns to leave unchanged: time, flow (Q) and temperature.
    non_conc = {"time", "Q", "T (C)", "T (F)"}

    # Soluble/particulate concentration state variables (mg/L) are the ADM1
    # S_* and X_* columns. Convert them to kg/m3 by dividing by 1000.
    conc_cols = [
        c for c in df.columns
        if c not in non_conc and (c.startswith("S_") or c.startswith("X_"))
    ]

    if not conc_cols:
        msg = (
            f"convert_solubles: no soluble concentration columns (S_*/X_*) found in "
            f"{input1}; columns present: {list(df.columns)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    df[conc_cols] = df[conc_cols] / 1000.0
    faasr_log(
        f"convert_solubles: converted {len(conc_cols)} concentration columns "
        f"from mg/L to kg/m3 (/1000): {conc_cols}"
    )

    df.to_csv(local_out, index=False)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"convert_solubles: wrote {output1} to folder {folder}")
