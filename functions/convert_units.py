"""FaaSr step 1: convert-units.

Reverse the field-instrument units back to native ADM1 units on the raw
digester influent file:

  * Q          : MGD           -> m3/d        (multiply by 3785.411784)
  * temperature: degrees F     -> degrees C   (convert AND rename "T (F)" -> "T")
  * 22 COD cols: mg/L (g/m3)   -> kg COD/m3   (divide by 1000)
                 - 10 solubles (S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac,
                   S_h2, S_ch4, S_I)
                 - 12 particulates (X_ch, X_pr, X_li, X_I, X_xc, X_su, X_aa,
                   X_fa, X_c4, X_pro, X_ac, X_h2)

The four non-COD concentration columns (S_IC, S_IN, S_cation, S_anion) are
already in native ADM1 units (kmole/m3) and are left untouched.
"""

try:
    from FaaSr_py.client.py_client_stubs import faasr_get_file, faasr_put_file, faasr_log
except Exception:  # pragma: no cover - stubs are injected into globals at runtime
    pass

import pandas as pd

# 10 soluble COD state variables (kg COD/m3 after conversion)
COD_SOLUBLE = ["S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro",
               "S_ac", "S_h2", "S_ch4", "S_I"]
# 12 particulate COD state variables (kg COD/m3 after conversion)
COD_PARTICULATE = ["X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
                   "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I"]
# 22 COD columns total
COD_COLUMNS = COD_SOLUBLE + COD_PARTICULATE
# Left completely untouched (already in kmole/m3)
UNTOUCHED = ["S_IC", "S_IN", "S_cation", "S_anion"]

MGD_TO_M3_PER_DAY = 3785.411784


def convert_units(folder, input_file="digester_influent_raw.csv",
                  output_file="influent_units_converted.csv"):
    faasr_log(f"convert_units: downloading {folder}/{input_file}")
    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file="raw_influent.csv")

    df = pd.read_csv("raw_influent.csv")

    # --- Flow: MGD -> m3/d (keep the column name "Q") ---
    if "Q" in df.columns:
        df["Q"] = df["Q"] * MGD_TO_M3_PER_DAY
        faasr_log("convert_units: converted Q from MGD to m3/d")
    else:
        faasr_log("convert_units: WARNING - no 'Q' column found")

    # --- Temperature: degrees F -> degrees C, rename "T (F)" -> "T" ---
    temp_col = None
    for cand in ["T (F)", "T(F)", "T_F", "T (degF)"]:
        if cand in df.columns:
            temp_col = cand
            break
    if temp_col is not None:
        df[temp_col] = (df[temp_col] - 32.0) * 5.0 / 9.0
        df = df.rename(columns={temp_col: "T"})
        faasr_log(f"convert_units: converted '{temp_col}' F->C and renamed to 'T'")
    else:
        faasr_log("convert_units: WARNING - no Fahrenheit temperature column found")

    # --- 22 COD columns: divide by 1000 (mg/L -> kg COD/m3) ---
    converted = []
    for col in COD_COLUMNS:
        if col in df.columns:
            df[col] = df[col] / 1000.0
            converted.append(col)
    faasr_log(f"convert_units: divided {len(converted)} COD columns by 1000 "
              f"(expected 22): {converted}")

    # --- Sanity: the 4 untouched columns must remain present and unmodified ---
    missing_untouched = [c for c in UNTOUCHED if c not in df.columns]
    if missing_untouched:
        faasr_log(f"convert_units: WARNING - missing untouched columns: {missing_untouched}")

    df.to_csv(output_file, index=False)
    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"convert_units: wrote {folder}/{output_file}")
