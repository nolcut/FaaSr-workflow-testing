def convert_units(folder: str, input1: str, output1: str) -> None:
    """Reverse field units back to ADM1 units for the raw digester influent series.

    - Q: MGD -> m3/d (multiply by 3785.41)
    - T (F): degrees Fahrenheit -> degrees Celsius, (F-32)*5/9, column renamed to 'T (C)'
    - All 22 COD state variables (10 soluble + 12 particulate) divided by 1000.
      S_IC, S_IN, S_cation and S_anion are left untouched.
    """
    import pandas as pd

    MGD_TO_M3D = 3785.41

    # The 22 COD-based ADM1 state variables (COD basis, mg/L -> g/L when /1000).
    # 10 soluble COD columns (S_IC, S_IN, S_cation, S_anion are NOT COD -> excluded).
    soluble_cod = [
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro",
        "S_ac", "S_h2", "S_ch4", "S_I",
    ]
    # 12 particulate COD columns.
    particulate_cod = [
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
        "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
    ]
    cod_columns = soluble_cod + particulate_cod

    faasr_log(f"convert_units: downloading raw influent '{input1}' from folder '{folder}'")
    local_in = "digester_influent_raw.csv"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)
    faasr_log(f"convert_units: read {len(df)} rows, {len(df.columns)} columns")

    # --- Flow: MGD -> m3/d ---
    if "Q" not in df.columns:
        msg = "convert_units: required flow column 'Q' not found in input CSV"
        faasr_log(msg)
        raise ValueError(msg)
    df["Q"] = df["Q"] * MGD_TO_M3D

    # --- Temperature: F -> C, and rename the column ---
    temp_col = None
    for cand in ("T (F)", "T(F)", "T_F"):
        if cand in df.columns:
            temp_col = cand
            break
    if temp_col is None:
        msg = "convert_units: required Fahrenheit temperature column 'T (F)' not found in input CSV"
        faasr_log(msg)
        raise ValueError(msg)
    df[temp_col] = (df[temp_col] - 32.0) * 5.0 / 9.0
    df = df.rename(columns={temp_col: "T (C)"})

    # --- COD columns: divide by 1000 ---
    missing = [c for c in cod_columns if c not in df.columns]
    if missing:
        msg = f"convert_units: expected COD columns missing from input CSV: {missing}"
        faasr_log(msg)
        raise ValueError(msg)
    df[cod_columns] = df[cod_columns] / 1000.0
    faasr_log(f"convert_units: divided {len(cod_columns)} COD columns by 1000")

    local_out = "influent_converted.csv"
    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"convert_units: wrote converted influent '{output1}' to folder '{folder}'")
