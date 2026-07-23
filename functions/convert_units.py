# Step 1: convert-units
# Reverse field/engineering units back to ADM1 units on the RAW digester influent.
#   - Q:  MGD  -> m3/d
#   - T:  degF -> degC   (convert the values AND rename the column to "T")
#   - divide ALL 22 COD columns by 1000 (10 solubles S_* + 12 particulates X_*)
#   - leave S_IC, S_IN, S_cation, S_anion untouched

# 10 soluble COD state variables (all in kg COD / m^3 after /1000)
COD_SOLUBLE = ["S_su", "S_aa", "S_fa", "S_va", "S_bu",
               "S_pro", "S_ac", "S_h2", "S_ch4", "S_I"]
# 12 particulate COD state variables
COD_PARTICULATE = ["X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
                   "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I"]
COD_COLUMNS = COD_SOLUBLE + COD_PARTICULATE            # 22 columns
UNTOUCHED = ["S_IC", "S_IN", "S_cation", "S_anion"]    # left as-is

MGD_TO_M3D = 3785.411784   # 1 US million gallons/day -> m^3/day

# candidate raw column names for the online sensors
Q_CANDIDATES = ["Q", "Q_MGD", "Q(MGD)", "Flow_MGD", "flow", "Flow"]
T_CANDIDATES = ["T_F", "T(F)", "T (F)", "TF", "Temp_F", "T_degF", "T_fahrenheit"]


def convert_units(folder, input_file="digester_influent_raw.csv",
                  output_file="influent_converted.csv"):
    import pandas as pd

    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file=input_file)
    df = pd.read_csv(input_file)

    # --- Flow: MGD -> m3/d ---
    for c in Q_CANDIDATES:
        if c in df.columns:
            df[c] = df[c].astype(float) * MGD_TO_M3D
            if c != "Q":
                df = df.rename(columns={c: "Q"})
            faasr_log(f"convert_units: converted flow column '{c}' MGD -> m3/d")
            break

    # --- Temperature: degF -> degC, convert AND rename to "T" ---
    for c in T_CANDIDATES:
        if c in df.columns:
            df[c] = (df[c].astype(float) - 32.0) * 5.0 / 9.0
            df = df.rename(columns={c: "T"})
            faasr_log(f"convert_units: converted+renamed temperature '{c}' degF -> degC as 'T'")
            break

    # --- Divide the 22 COD columns by 1000 ---
    converted = []
    for c in COD_COLUMNS:
        if c in df.columns:
            df[c] = df[c].astype(float) / 1000.0
            converted.append(c)
    faasr_log(f"convert_units: divided {len(converted)} COD columns by 1000 "
              f"(left {UNTOUCHED} untouched)")

    df.to_csv(output_file, index=False)
    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"convert_units: wrote {folder}/{output_file}")
