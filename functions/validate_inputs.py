import pandas as pd
import numpy as np


def validate_inputs(folder, influent_file, initial_file):
    """
    FaaSr function: validate the PyADM1 input CSV files.

    Downloads digester_influent.csv and digester_initial.csv from the S3
    datastore, checks that they contain all state-variable columns that
    PyADM1 requires, that there are no missing/NaN values, and that the
    influent has a monotonically increasing `time` column with at least two
    rows (needed by the dynamic simulation loop).

    Returns True when both inputs are valid and False otherwise. The boolean
    return value is used by the workflow's conditional InvokeNext to gate the
    simulation step.
    """

    # --- Columns required by PyADM1.py ---------------------------------------
    # Influent (feed) file: a `time` column plus the 26 influent state vars.
    influent_required = [
        "time",
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2",
        "S_ch4", "S_IC", "S_IN", "S_I",
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4",
        "X_pro", "X_ac", "X_h2", "X_I",
        "S_cation", "S_anion",
    ]

    # Initial reactor-state file: the 26 state vars plus the ion / gas states
    # that PyADM1 reads from initial_state[...][0].
    initial_required = [
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2",
        "S_ch4", "S_IC", "S_IN", "S_I",
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4",
        "X_pro", "X_ac", "X_h2", "X_I",
        "S_cation", "S_anion",
        "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion",
        "S_hco3_ion", "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
    ]

    # --- Download inputs from S3 --------------------------------------------
    faasr_get_file(remote_folder=folder, remote_file=influent_file,
                   local_folder=".", local_file="digester_influent.csv")
    faasr_get_file(remote_folder=folder, remote_file=initial_file,
                   local_folder=".", local_file="digester_initial.csv")

    errors = []

    def _check(df, name, required, min_rows):
        # Missing columns
        missing = [c for c in required if c not in df.columns]
        if missing:
            errors.append(f"{name}: missing required columns: {missing}")
            return
        # Row count
        if len(df) < min_rows:
            errors.append(f"{name}: needs at least {min_rows} row(s), found {len(df)}")
        # NaN / non-numeric
        sub = df[required]
        n_nan = int(sub.isna().sum().sum())
        if n_nan > 0:
            errors.append(f"{name}: contains {n_nan} missing/NaN value(s)")
        if not all(np.issubdtype(dt, np.number) for dt in sub.dtypes):
            bad = [c for c in required if not np.issubdtype(df[c].dtype, np.number)]
            errors.append(f"{name}: non-numeric column(s): {bad}")

    # --- Validate influent ---------------------------------------------------
    try:
        influent = pd.read_csv("digester_influent.csv")
        _check(influent, "influent", influent_required, min_rows=2)
        if "time" in influent.columns:
            t = influent["time"]
            if not t.is_monotonic_increasing:
                errors.append("influent: 'time' column is not monotonically increasing")
    except Exception as e:
        errors.append(f"influent: could not be read ({e})")

    # --- Validate initial ----------------------------------------------------
    try:
        initial = pd.read_csv("digester_initial.csv")
        _check(initial, "initial", initial_required, min_rows=1)
    except Exception as e:
        errors.append(f"initial: could not be read ({e})")

    # --- Report --------------------------------------------------------------
    if errors:
        faasr_log("Input validation FAILED:")
        for err in errors:
            faasr_log("  - " + err)
        faasr_log("Simulation step will be skipped.")
        return False

    faasr_log(
        f"Input validation PASSED: influent={influent_file} "
        f"({len(influent)} rows), initial={initial_file} ({len(initial)} rows). "
        "All required columns present, numeric, and non-missing."
    )
    return True
