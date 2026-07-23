import pandas as pd


def fill_gaps(folder="PyADM1-orig",
              input_file="influent_step1_units.csv",
              output_file="influent_step2_filled.csv"):
    """Step 2 - forward-fill missing S_cation and S_anion values.

    Sensor/lab dropouts in the ionic strength channels are carried forward from
    the last valid reading. A leading gap (no prior value) is back-filled so the
    simulation always has a defined ionic balance at t0.
    """
    faasr_get_file(remote_folder=folder, remote_file=input_file, local_file="in.csv")
    df = pd.read_csv("in.csv")

    for col in ["S_cation", "S_anion"]:
        if col not in df.columns:
            faasr_log(f"fill_gaps WARNING: column '{col}' not found; skipping")
            continue
        n_missing = int(df[col].isna().sum())
        df[col] = df[col].ffill().bfill()
        faasr_log(f"fill_gaps: forward-filled {n_missing} missing values in '{col}'")

    df.to_csv("filled.csv", index=False)
    faasr_put_file(local_file="filled.csv", remote_folder=folder, remote_file=output_file)
    faasr_log(f"fill_gaps: wrote {folder}/{output_file}")
