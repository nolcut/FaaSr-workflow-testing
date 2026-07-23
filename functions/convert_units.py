import pandas as pd

# Step 1: convert-units
# Reverse field/plant sensor units back into the ADM1 (BSM2) units that
# PyADM1 expects.
#   - Q:  US MGD -> m3/d
#   - T:  degrees Fahrenheit -> degrees Celsius (convert AND rename column)
#   - all 22 COD-based state columns (soluble S_* + particulate X_*) are
#     reported in field units of g COD/m3 (= mg/L) and must be divided by
#     1000 to become kg COD/m3.
# S_IC, S_IN (kmole/m3) and S_cation, S_anion (kmole/m3) are NOT COD based
# and are left untouched.

FOLDER = "PyADM1-orig"

# 1 US million gallons per day -> cubic metres per day
MGD_TO_M3D = 3785.411784

# The 22 COD columns: 10 solubles + 12 particulates.
COD_COLUMNS = [
    # soluble COD (kg COD/m3)
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2",
    "S_ch4", "S_I",
    # particulate COD (kg COD/m3)
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4",
    "X_pro", "X_ac", "X_h2", "X_I",
]


def convert_units():
    faasr_log("convert-units: downloading raw digester influent")
    faasr_get_file(
        server_name="S3",
        remote_folder=FOLDER,
        remote_file="digester_influent_raw.csv",
        local_folder=".",
        local_file="digester_influent_raw.csv",
    )

    df = pd.read_csv("digester_influent_raw.csv")

    # --- Flow: MGD -> m3/d ---
    if "Q" in df.columns:
        df["Q"] = df["Q"].astype(float) * MGD_TO_M3D
        faasr_log("convert-units: converted Q from MGD to m3/d")

    # --- Temperature: F -> C, convert AND rename the column ---
    temp_src = None
    for candidate in ("T_F", "T", "Temp", "T_op"):
        if candidate in df.columns:
            temp_src = candidate
            break
    if temp_src is not None:
        df["T_C"] = (df[temp_src].astype(float) - 32.0) * 5.0 / 9.0
        if temp_src != "T_C":
            df = df.drop(columns=[temp_src])
        faasr_log(f"convert-units: converted temperature '{temp_src}' (F) -> 'T_C' (C)")

    # --- COD columns: divide by 1000 (leave S_IC, S_IN, S_cation, S_anion) ---
    present = [c for c in COD_COLUMNS if c in df.columns]
    df[present] = df[present].astype(float) / 1000.0
    faasr_log(f"convert-units: divided {len(present)} COD columns by 1000")

    df.to_csv("influent_converted.csv", index=False)
    faasr_put_file(
        server_name="S3",
        local_folder=".",
        local_file="influent_converted.csv",
        remote_folder=FOLDER,
        remote_file="influent_converted.csv",
    )
    faasr_log("convert-units: wrote influent_converted.csv")
