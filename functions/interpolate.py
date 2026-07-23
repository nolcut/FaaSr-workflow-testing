"""FaaSr step 4: interpolate.

The 26 lab-measured composition columns are weekly grab samples that were
recorded into the 15-minute time base by holding each value constant for the
whole week (a zero-order hold / step signal). This step treats each held block
as a single weekly sample located at the block's start, then linearly
interpolates between consecutive weekly samples onto the native 15-minute grid.

The 26 lab columns = 10 soluble COD + 12 particulate COD + 4 untouched
(S_IC, S_IN, S_cation, S_anion). Online sensor channels (time, Q, T) are left
on their own 15-minute grid and are NOT interpolated here.
"""

try:
    from FaaSr_py.client.py_client_stubs import faasr_get_file, faasr_put_file, faasr_log
except Exception:  # pragma: no cover
    pass

import pandas as pd

COD_SOLUBLE = ["S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro",
               "S_ac", "S_h2", "S_ch4", "S_I"]
COD_PARTICULATE = ["X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
                   "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I"]
UNTOUCHED = ["S_IC", "S_IN", "S_cation", "S_anion"]
# 26 weekly-held lab columns
LAB_COLUMNS = COD_SOLUBLE + COD_PARTICULATE + UNTOUCHED


def interpolate(folder, input_file="influent_despiked.csv",
                output_file="digester_influent.csv"):
    faasr_log(f"interpolate: downloading {folder}/{input_file}")
    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file="in.csv")

    df = pd.read_csv("in.csv")
    if "time" in df.columns:
        df = df.sort_values("time").reset_index(drop=True)
        time_index = df["time"].to_numpy()
    else:
        faasr_log("interpolate: WARNING - no 'time' column; using row order as time base")
        time_index = df.index.to_numpy()

    present = [c for c in LAB_COLUMNS if c in df.columns]
    faasr_log(f"interpolate: interpolating {len(present)} lab columns "
              f"(expected 26): {present}")

    for col in present:
        s = df[col]
        # Anchor points = start of each weekly held block (value changes from
        # the previous row); everything else is treated as an un-sampled hold.
        changed = s.ne(s.shift())
        changed.iloc[0] = True
        anchored = s.where(changed)
        # Interpolate against the real time base so spacing is respected.
        tmp = pd.Series(anchored.to_numpy(), index=time_index)
        tmp = tmp.interpolate(method="index").ffill().bfill()
        df[col] = tmp.to_numpy()

    df.to_csv(output_file, index=False)
    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"interpolate: wrote cleaned influent {folder}/{output_file}")
