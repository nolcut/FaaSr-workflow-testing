# Step 4: interpolate
# The 26 lab (state-variable) columns are reported weekly and were stored
# "held" (the weekly value repeated on every high-frequency row). Treat each
# distinct held value as a single weekly grab sample, then interpolate linearly
# against the time axis to the native 15-minute resolution of the influent file.
#
# The 26 lab columns = 22 COD columns + 4 untouched ion/carbon/nitrogen columns.

LAB_COLUMNS = [
    # 10 soluble COD
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4", "S_I",
    # 12 particulate COD
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
    "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
    # 4 inorganic / ion columns
    "S_IC", "S_IN", "S_cation", "S_anion",
]


def interpolate_lab(folder, input_file="influent_despiked.csv",
                    output_file="digester_influent.csv"):
    import pandas as pd
    import numpy as np

    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file=input_file)
    df = pd.read_csv(input_file)

    # time axis used as the interpolation index (days). Fall back to row index.
    if "time" in df.columns:
        t = pd.to_numeric(df["time"], errors="coerce").to_numpy()
    else:
        t = np.arange(len(df), dtype=float)

    n_cols = 0
    for c in LAB_COLUMNS:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        # weekly grab samples = rows where the held value changes (first of each block)
        anchor = s.where(s.ne(s.shift()))
        # linear interpolation against the (possibly irregular) time axis
        tmp = pd.Series(anchor.to_numpy(), index=t)
        tmp = tmp.interpolate(method="index", limit_direction="both")
        df[c] = tmp.to_numpy()
        n_cols += 1

    faasr_log(f"interpolate_lab: interpolated {n_cols} weekly lab columns to 15-min resolution")

    # This is the final cleaned influent consumed by PyADM1 (expects this exact name).
    df.to_csv(output_file, index=False)
    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"interpolate_lab: wrote cleaned influent {folder}/{output_file}")
