def interpolate(folder: str, input1: str, output1: str) -> None:
    """Turn the 26 weekly-held lab columns into smooth 15-minute trajectories.

    Each of the 26 ADM1 influent composition columns holds a single lab value
    (step-constant) across the 15-minute timestamps between weekly samples. The
    actual weekly sample points are the timestamps where a column takes a new
    (changed) value. Between successive sample points the held stretch is replaced
    by a straight-line (time-linear) interpolation, so the step profile becomes a
    continuous trajectory at the dataset's native 15-minute resolution. The time
    index, Q, T and all derived (ion/gas) columns are left exactly unchanged.
    """
    import pandas as pd
    import numpy as np

    # The 26 weekly-sampled lab columns: the ADM1 influent state variables that
    # PyADM1 reads from digester_influent.csv (12 soluble S_*, 12 particulate X_*,
    # plus S_cation and S_anion). Q and T are continuous operational sensors and the
    # S_*_ion / S_co2 / S_gas_* columns are derived algebraic states, so none of
    # those are interpolated here.
    lab_columns = [
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
        "S_IC", "S_IN", "S_I",
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
        "X_ac", "X_h2", "X_I",
        "S_cation", "S_anion",
    ]

    faasr_log(f"interpolate: downloading despiked influent '{input1}' from folder '{folder}'")
    local_in = "influent_despiked.csv"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)
    faasr_log(f"interpolate: read {len(df)} rows, {len(df.columns)} columns")

    if "time" not in df.columns:
        msg = "interpolate: required 'time' column not found in input CSV"
        faasr_log(msg)
        raise ValueError(msg)
    missing = [c for c in lab_columns if c not in df.columns]
    if missing:
        msg = f"interpolate: expected lab columns missing from input CSV: {missing}"
        faasr_log(msg)
        raise ValueError(msg)

    t = df["time"].astype(float).to_numpy()

    for col in lab_columns:
        s = df[col].astype(float)
        # Weekly sample points: the first row plus every row where the held value
        # changes. s.ne(s.shift()) is True at index 0 (shift is NaN) and at each
        # transition, so these mark the actual weekly measurements.
        sample_mask = s.ne(s.shift()).to_numpy()
        xp = t[sample_mask]
        fp = s.to_numpy()[sample_mask]
        # np.interp linearly interpolates between successive sample points and holds
        # the first/last sample value outside the sampled range (so a trailing held
        # stretch keeps its last measured value, and a single sample stays constant).
        df[col] = np.interp(t, xp, fp)
        faasr_log(f"interpolate: {col} — {len(xp)} weekly sample point(s) -> interpolated")

    local_out = "digester_influent.csv"
    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"interpolate: wrote cleaned influent '{output1}' to folder '{folder}'")
