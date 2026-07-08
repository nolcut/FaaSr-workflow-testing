import pandas as pd

# Required columns for the ADM1 influent (feed) time series.
# These are every column read by the PyADM1 driver's setInfluent() plus 'time'.
INFLUENT_REQUIRED = [
    "time",
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
]

# Required columns for the ADM1 initial reactor state (single row of values).
INITIAL_REQUIRED = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion",
    "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
]


def _validate_frame(df, required, name, min_rows):
    """Validate a dataframe: required columns present, enough rows, numeric and
    free of missing values. Returns a list of human-readable error strings."""
    errors = []

    missing = [c for c in required if c not in df.columns]
    if missing:
        errors.append(f"{name}: missing required columns: {missing}")

    if len(df) < min_rows:
        errors.append(f"{name}: expected at least {min_rows} row(s), found {len(df)}")

    # Only inspect columns that actually exist to avoid KeyErrors.
    for col in [c for c in required if c in df.columns]:
        series = pd.to_numeric(df[col], errors="coerce")
        n_bad = int(series.isna().sum())
        if n_bad > 0:
            errors.append(
                f"{name}: column '{col}' has {n_bad} non-numeric or missing value(s)"
            )

    return errors


def validate_inputs(folder, influent_file, initial_file):
    """
    Validate the ADM1 influent and initial-state CSV inputs before simulation.

    Downloads both CSV files from the S3 data store, checks that all required
    columns are present, that the files are non-empty, and that every required
    value is numeric and non-missing. Raises ValueError (failing the workflow)
    if validation fails so that PyADM1 never runs on bad input.
    """
    faasr_get_file(remote_folder=folder, remote_file=influent_file,
                   local_file="digester_influent.csv")
    faasr_get_file(remote_folder=folder, remote_file=initial_file,
                   local_file="digester_initial.csv")

    influent = pd.read_csv("digester_influent.csv")
    initial = pd.read_csv("digester_initial.csv")

    faasr_log(
        f"validate_inputs: loaded influent ({influent.shape[0]} rows, "
        f"{influent.shape[1]} cols) and initial ({initial.shape[0]} rows, "
        f"{initial.shape[1]} cols)"
    )

    errors = []
    # Influent is a dynamic feed time series -> needs >= 2 rows to simulate.
    errors += _validate_frame(influent, INFLUENT_REQUIRED, "influent", min_rows=2)
    # Initial state is a single row of reactor concentrations.
    errors += _validate_frame(initial, INITIAL_REQUIRED, "initial", min_rows=1)

    # The driver integrates between successive 'time' values, so time must be
    # present and strictly increasing.
    if "time" in influent.columns:
        t = pd.to_numeric(influent["time"], errors="coerce")
        if not t.is_monotonic_increasing or t.duplicated().any():
            errors.append("influent: 'time' column must be strictly increasing")

    if errors:
        for e in errors:
            faasr_log(f"validate_inputs: VALIDATION ERROR - {e}")
        raise ValueError("Input validation failed:\n" + "\n".join(errors))

    faasr_log("validate_inputs: all checks passed; inputs are valid for PyADM1")
