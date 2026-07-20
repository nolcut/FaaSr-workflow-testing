import pandas as pd
import numpy as np

# High-frequency sensor columns that are already at 15-min resolution — leave unchanged.
# The remaining 26 columns are weekly-held lab measurements that need interpolation.
HIGH_FREQ_COLS = {
    "time", "Q", "T",
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion",
    "S_hco3_ion", "S_co2", "S_nh3", "S_nh4_ion",
    "S_gas_h2", "S_gas_ch4", "S_gas_co2",
}


def interpolate(folder: str, input1: str, output1: str) -> None:
    local_in = "influent_despiked.csv"
    local_out = "influent_interpolated.csv"

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"interpolate: read {input1}")

    df = pd.read_csv(local_in)

    lab_cols = [c for c in df.columns if c not in HIGH_FREQ_COLS]
    if len(lab_cols) != 26:
        faasr_log(f"interpolate: WARNING — expected 26 lab columns, found {len(lab_cols)}: {lab_cols}")

    faasr_log(f"interpolate: interpolating {len(lab_cols)} lab columns using time-index method")

    # Use the numeric time column as the interpolation axis so gaps of different
    # lengths are handled proportionally (equivalent to method='time' for a
    # DatetimeIndex, but works with the numeric day-based time column).
    df_indexed = df.set_index("time")
    df_indexed[lab_cols] = df_indexed[lab_cols].interpolate(method="index")
    df = df_indexed.reset_index()

    nan_remaining = df[lab_cols].isna().sum().sum()
    if nan_remaining > 0:
        faasr_log(f"interpolate: WARNING — {nan_remaining} NaN values remain after interpolation (leading/trailing gaps)")

    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"interpolate: wrote {output1}")
