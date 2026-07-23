import pandas as pd
import numpy as np

# The 26 lab-measured influent columns.  In the raw record each lab value is
# "held" constant for a whole week (a step function) because the lab only
# samples weekly.  We treat each held block as a single weekly sample located
# at the block's start and linearly interpolate between weekly samples onto the
# existing 15-min sensor grid.
SOLUBLE_COD = ["S_su", "S_aa", "S_fa", "S_va", "S_bu",
               "S_pro", "S_ac", "S_h2", "S_ch4", "S_I"]
PARTICULATE_COD = ["X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
                   "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I"]
LAB_COLUMNS = SOLUBLE_COD + ["S_IC", "S_IN"] + PARTICULATE_COD + ["S_cation", "S_anion"]
# = 10 + 2 + 12 + 2 = 26 columns


def interpolate_weekly(folder, input_file, output_file):
    """Step 4 - treat the 26 weekly-held lab columns as weekly samples and
    interpolate them to the 15-min sensor resolution."""
    faasr_get_file(server_name="S3", remote_folder=folder,
                   remote_file=input_file, local_file="in.csv")
    df = pd.read_csv("in.csv")

    # x axis for interpolation (elapsed time in days if present, else row index)
    if "time" in df.columns:
        x = df["time"].astype(float)
    else:
        x = pd.Series(np.arange(len(df)), dtype=float)

    n_interp = 0
    for col in LAB_COLUMNS:
        if col not in df.columns:
            continue
        vals = df[col].astype(float)
        # A weekly sample = the first row of each held block (value changes).
        changed = vals.ne(vals.shift())
        changed.iloc[0] = True
        samples = vals.where(changed)          # keep sample points, NaN elsewhere
        # linear interpolation across the time axis, extend to both ends
        tmp = pd.DataFrame({"x": x.values, "y": samples.values}).set_index("x")
        df[col] = tmp["y"].interpolate(method="index",
                                       limit_direction="both").values
        n_interp += 1

    df.to_csv(output_file, index=False)
    faasr_put_file(server_name="S3", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log("interpolate_weekly: interpolated {} weekly lab columns to the "
              "15-min grid; wrote {}/{}".format(n_interp, folder, output_file))
