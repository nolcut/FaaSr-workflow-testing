import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Column groups (ADM1 state variables)
# ---------------------------------------------------------------------------
# 10 soluble COD species (kg COD / m^3)
SOLUBLE_COD = ["S_su", "S_aa", "S_fa", "S_va", "S_bu",
               "S_pro", "S_ac", "S_h2", "S_ch4", "S_I"]
# 12 particulate COD species (kg COD / m^3)
PARTICULATE_COD = ["X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
                   "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I"]
# 22 COD columns total = 10 soluble + 12 particulate
COD_COLUMNS = SOLUBLE_COD + PARTICULATE_COD
# The only columns left untouched (they are NOT COD units)
UNTOUCHED = ["S_IC", "S_IN", "S_cation", "S_anion"]

# 1 US million-gallons-per-day == 3785.411784 m^3/d
MGD_TO_M3D = 3785.411784


def convert_units(folder, input_file, output_file):
    """Step 1 - reverse field units back to native ADM1 units.

    * Q : MGD              -> m^3/d
    * T : degrees F        -> degrees C  (column is converted AND renamed to T_C)
    * all 22 COD columns   -> divided by 1000 (both S_* solubles and X_* particulates)
    * S_IC, S_IN, S_cation, S_anion are left exactly as-is
    """
    faasr_get_file(server_name="S3", remote_folder=folder,
                   remote_file=input_file, local_file="raw.csv")
    df = pd.read_csv("raw.csv")

    # --- Q : MGD -> m^3/d ------------------------------------------------
    if "Q" in df.columns:
        df["Q"] = df["Q"].astype(float) * MGD_TO_M3D

    # --- T : Fahrenheit -> Celsius, and rename the column ----------------
    temp_col = None
    for candidate in ["T_F", "T (F)", "T_degF", "T"]:
        if candidate in df.columns:
            temp_col = candidate
            break
    if temp_col is not None:
        df[temp_col] = (df[temp_col].astype(float) - 32.0) * 5.0 / 9.0
        df = df.rename(columns={temp_col: "T_C"})

    # --- 22 COD columns : divide by 1000 ---------------------------------
    converted = []
    for col in COD_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(float) / 1000.0
            converted.append(col)

    df.to_csv(output_file, index=False)
    faasr_put_file(server_name="S3", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(
        "convert_units: Q->m3/d, T(F)->T_C, divided {} COD columns by 1000; "
        "left {} untouched; wrote {}/{}".format(
            len(converted), UNTOUCHED, folder, output_file))
