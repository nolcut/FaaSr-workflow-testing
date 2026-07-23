import pandas as pd
import numpy as np

# The 22 COD-based columns that must be divided by 1000 (mg/L field units -> kg/m3 ADM1 units).
# 10 soluble COD species (S_*) ...
SOLUBLE_COD = ["S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4", "S_I"]
# ... and 12 particulate COD species (X_*).
PARTICULATE_COD = ["X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4",
                   "X_pro", "X_ac", "X_h2", "X_I"]
COD_COLUMNS = SOLUBLE_COD + PARTICULATE_COD  # exactly 22 columns

# These stay untouched (they are in kmole units, not COD).
UNTOUCHED = ["S_IC", "S_IN", "S_cation", "S_anion"]

# Candidate raw header names for the flow and temperature sensor columns.
Q_CANDIDATES = ["Q", "Q_MGD", "Q (MGD)", "Q_mgd", "Flow", "Flowrate", "flow"]
T_CANDIDATES = ["T", "T_F", "T (F)", "T_degF", "Temp", "Temperature", "temp"]

MGD_TO_M3D = 3785.411784  # 1 US million gallons/day = 3785.411784 m3/day


def _find_column(df, candidates, label):
    for c in candidates:
        if c in df.columns:
            return c
    raise ValueError(f"Could not find a {label} column. Looked for {candidates}; "
                     f"available columns: {list(df.columns)}")


def convert_units(folder="PyADM1-orig",
                  input_file="digester_influent_raw.csv",
                  output_file="influent_step1_units.csv"):
    """Step 1 - convert field units back to ADM1 units.

    * Q: MGD -> m3/d
    * T: Fahrenheit -> Celsius, AND rename the column to 'T_C'
    * All 22 COD columns (S_* solubles + X_* particulates): divide by 1000
    * S_IC, S_IN, S_cation, S_anion: left untouched
    """
    faasr_get_file(remote_folder=folder, remote_file=input_file, local_file="raw.csv")
    df = pd.read_csv("raw.csv")

    # --- Flow: MGD -> m3/d (keep the column named "Q") ---
    q_col = _find_column(df, Q_CANDIDATES, "flow (Q)")
    df[q_col] = df[q_col].astype(float) * MGD_TO_M3D
    if q_col != "Q":
        df = df.rename(columns={q_col: "Q"})

    # --- Temperature: Fahrenheit -> Celsius, rename column to T_C ---
    t_col = _find_column(df, T_CANDIDATES, "temperature (T)")
    df[t_col] = (df[t_col].astype(float) - 32.0) * 5.0 / 9.0
    df = df.rename(columns={t_col: "T_C"})

    # --- Divide the 22 COD columns by 1000 ---
    converted = []
    for col in COD_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(float) / 1000.0
            converted.append(col)
        else:
            faasr_log(f"convert_units WARNING: expected COD column '{col}' not found")
    faasr_log(f"convert_units: divided {len(converted)} COD columns by 1000: {converted}")

    for col in UNTOUCHED:
        if col not in df.columns:
            faasr_log(f"convert_units WARNING: untouched column '{col}' not present")

    df.to_csv("units_out.csv", index=False)
    faasr_put_file(local_file="units_out.csv", remote_folder=folder, remote_file=output_file)
    faasr_log(f"convert_units: wrote {folder}/{output_file} with columns {list(df.columns)}")
