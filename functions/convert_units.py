import pandas as pd
import io

COD_COLUMNS = [
    # Soluble COD fractions
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac",
    "S_h2", "S_ch4", "S_I",
    # Particulate COD fractions
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa",
    "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
]


def convert_units(folder: str, input1: str, output1: str) -> None:
    local_in = "influent_raw.csv"
    local_out = "influent_converted.csv"

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"convert_units: read {input1}")

    df = pd.read_csv(local_in)

    # 1. Convert Q from MGD to m3/d
    if "Q" not in df.columns:
        faasr_log("convert_units: ERROR — column Q not found")
        raise ValueError("Column Q not found in input")
    df["Q"] = df["Q"] * 3785.41
    faasr_log("convert_units: Q converted MGD -> m3/d")

    # 2. Convert temperature F -> C and rename column to T
    temp_col = "T (F)"
    if temp_col not in df.columns:
        faasr_log(f"convert_units: ERROR — temperature column '{temp_col}' not found")
        raise ValueError(f"Temperature column '{temp_col}' not found in input")
    df["T"] = (df[temp_col] - 32) * 5 / 9
    df = df.drop(columns=[temp_col])
    faasr_log("convert_units: temperature converted F -> C and column renamed to T")

    # 3. Divide the 22 COD-fraction columns by 1000 (mg/L -> kgCOD/m3)
    missing = [c for c in COD_COLUMNS if c not in df.columns]
    if missing:
        faasr_log(f"convert_units: ERROR — missing COD columns: {missing}")
        raise ValueError(f"Missing expected COD columns: {missing}")
    df[COD_COLUMNS] = df[COD_COLUMNS] / 1000.0
    faasr_log("convert_units: 22 COD columns divided by 1000 (mg/L -> kgCOD/m3)")

    # S_IC, S_IN, S_cation, S_anion left untouched per spec

    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"convert_units: wrote {output1}")
