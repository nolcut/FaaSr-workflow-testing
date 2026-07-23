import pandas as pd

# Step 4: interpolate
# The 26 ADM1 composition columns come from a weekly lab assay. In the raw
# feed each weekly value is *held* (repeated) across every 15-min row until
# the next assay. That produces unphysical stair-steps. Treat each held run
# as a single weekly sample located at its first row, blank out the repeats,
# and linearly interpolate back onto the full 15-min grid so the influent
# forcing varies smoothly.
#
# Q and T_C are genuine 15-min sensor channels and are left as-is.

FOLDER = "PyADM1-orig"

# The 26 weekly-held lab columns (12 soluble + 12 particulate + 2 ionic).
LAB_COLUMNS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2",
    "S_ch4", "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4",
    "X_pro", "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
]


def interpolate():
    faasr_log("interpolate: downloading despiked influent")
    faasr_get_file(
        server_name="S3",
        remote_folder=FOLDER,
        remote_file="influent_despiked.csv",
        local_folder=".",
        local_file="influent_despiked.csv",
    )

    df = pd.read_csv("influent_despiked.csv")

    for col in LAB_COLUMNS:
        if col not in df.columns:
            continue
        s = df[col].astype(float)
        # Identify weekly sample points: the first row of every held run
        # (i.e. where the value changes from the previous row).
        changed = s.ne(s.shift())
        changed.iloc[0] = True
        sampled = s.where(changed)
        # Linear interpolation across the 15-min grid between weekly samples.
        df[col] = sampled.interpolate(method="linear", limit_direction="both")

    faasr_log(f"interpolate: interpolated {len(LAB_COLUMNS)} weekly lab columns to 15-min")

    # This is the fully cleaned influent that PyADM1 consumes.
    df.to_csv("digester_influent.csv", index=False)
    faasr_put_file(
        server_name="S3",
        local_folder=".",
        local_file="digester_influent.csv",
        remote_folder=FOLDER,
        remote_file="digester_influent.csv",
    )
    faasr_log("interpolate: wrote cleaned digester_influent.csv")
