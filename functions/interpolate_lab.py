import pandas as pd
import numpy as np

# The 26 weekly lab-analysed ADM1 state variables. In the raw record these are
# "held" (repeated) between weekly grab-sample measurements. Q and T_C are
# continuous sensor channels and are NOT interpolated here.
LAB_COLUMNS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
]


def interpolate_lab(folder="PyADM1-orig",
                    input_file="influent_step3_despiked.csv",
                    output_file="digester_influent.csv"):
    """Step 4 - treat the 26 weekly-held lab columns as weekly samples and
    interpolate them to the 15-min time grid.

    Each held segment starts at a true weekly grab sample; the repeated held
    values that follow are treated as unknowns (NaN) and replaced by a linear
    interpolation between consecutive weekly samples, producing a smooth 15-min
    ramp. The result is written as 'digester_influent.csv' (the name PyADM1
    expects).
    """
    faasr_get_file(remote_folder=folder, remote_file=input_file, local_file="in.csv")
    df = pd.read_csv("in.csv")

    # Use time as the interpolation axis when available so spacing is honoured.
    x = None
    if "time" in df.columns:
        x = pd.to_numeric(df["time"], errors="coerce")

    n_cols = 0
    for col in LAB_COLUMNS:
        if col not in df.columns:
            faasr_log(f"interpolate_lab WARNING: column '{col}' not found; skipping")
            continue

        s = df[col].astype(float)

        # Anchor points = the first row of each held run (i.e. where the value
        # changes from the previous row). These are the true weekly samples.
        is_anchor = s.ne(s.shift(1))
        is_anchor.iloc[0] = True
        anchored = s.where(is_anchor)

        if x is not None and x.notna().all():
            interp = pd.Series(
                np.interp(x, x[is_anchor], anchored[is_anchor]),
                index=df.index,
            )
        else:
            interp = anchored.interpolate(method="linear", limit_direction="both")

        df[col] = interp
        n_cols += 1

    faasr_log(f"interpolate_lab: interpolated {n_cols} weekly lab columns to the 15-min grid")

    df.to_csv("influent_interp.csv", index=False)
    faasr_put_file(local_file="influent_interp.csv", remote_folder=folder, remote_file=output_file)
    faasr_log(f"interpolate_lab: wrote cleaned influent to {folder}/{output_file}")
