import json
import math

import pandas as pd

# Column requirements derived directly from the PyADM1 simulation code
# (functions/original_pyadm1.py). The influent file is a time series of the
# 24 ADM1 feed state variables plus a leading `time` column; the initial file
# holds one row with the full reactor initial state (including ion / gas-phase
# variables read at index [0] by the simulator).
INFLUENT_REQUIRED_COLUMNS = [
    "time",
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
]

INITIAL_REQUIRED_COLUMNS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion",
    "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
]


def _validate_csv(local_path, label, required_columns, min_rows):
    """Validate one input CSV. Returns (checks_list, all_passed_bool)."""
    checks = []

    def record(name, passed, detail):
        checks.append({"check": name, "status": "PASS" if passed else "FAIL",
                       "detail": detail})
        return passed

    # 1. Parse as a well-formed CSV.
    try:
        df = pd.read_csv(local_path)
    except Exception as e:  # noqa: BLE001 - report any parse failure
        record("parse_csv", False, f"could not parse {label} as CSV: {e}")
        return checks, False
    record("parse_csv", True, f"parsed {label} as CSV")

    # 2. Non-empty with the minimum expected number of data rows.
    if not record("row_count", len(df) >= min_rows,
                  f"{len(df)} data row(s) found, need at least {min_rows}"):
        return checks, False

    # 3. Required columns present.
    missing = [c for c in required_columns if c not in df.columns]
    if not record("required_columns", not missing,
                  f"missing columns: {missing}" if missing
                  else f"all {len(required_columns)} required columns present"):
        return checks, False

    # 4. Required values numeric, non-missing, and finite.
    bad_numeric = []
    non_finite = []
    for col in required_columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        if coerced.isna().any():
            bad_numeric.append(col)
            continue
        if not all(math.isfinite(float(v)) for v in coerced):
            non_finite.append(col)
    numeric_ok = record(
        "numeric_values", not bad_numeric,
        f"non-numeric/missing values in: {bad_numeric}" if bad_numeric
        else "all required fields numeric with no missing values")
    finite_ok = record(
        "finite_values", not non_finite,
        f"infinite values in: {non_finite}" if non_finite
        else "all required fields finite")
    if not (numeric_ok and finite_ok):
        return checks, False

    # 5. Physically plausible ranges. ADM1 concentrations (kg COD/m^3,
    #    kmole/m^3) and simulation time are non-negative.
    negative = []
    for col in required_columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        if (coerced < 0).any():
            negative.append(col)
    range_ok = record(
        "value_ranges", not negative,
        f"negative (non-physical) values in: {negative}" if negative
        else "all required values within plausible (non-negative) range")

    # 6. Influent time column must be strictly increasing so the simulation
    #    can step forward through it.
    if "time" in required_columns:
        t = pd.to_numeric(df["time"], errors="coerce")
        monotonic = bool(t.is_monotonic_increasing) and bool((t.diff().dropna() > 0).all())
        record("time_monotonic", monotonic,
               "time column strictly increasing" if monotonic
               else "time column is not strictly increasing")

    passed = all(c["status"] == "PASS" for c in checks)
    return checks, passed


def validate_inputs(folder: str, input1: str, input2: str, output1: str) -> None:
    faasr_log(f"validate_inputs: validating '{input1}' and '{input2}' in folder '{folder}'")

    # Fetch the two external input CSVs from S3 using bare basenames.
    influent_local = "digester_influent_local.csv"
    initial_local = "digester_initial_local.csv"
    faasr_get_file(local_file=influent_local, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=initial_local, remote_folder=folder, remote_file=input2)

    influent_checks, influent_ok = _validate_csv(
        influent_local, input1, INFLUENT_REQUIRED_COLUMNS, min_rows=2)
    for c in influent_checks:
        faasr_log(f"[{input1}] {c['check']}: {c['status']} - {c['detail']}")

    initial_checks, initial_ok = _validate_csv(
        initial_local, input2, INITIAL_REQUIRED_COLUMNS, min_rows=1)
    for c in initial_checks:
        faasr_log(f"[{input2}] {c['check']}: {c['status']} - {c['detail']}")

    overall_ok = influent_ok and initial_ok
    report = {
        "workflow": "pyadm1_digester_simulation",
        "function": "validate_inputs",
        "folder": folder,
        "overall_status": "PASS" if overall_ok else "FAIL",
        "files": {
            input1: {
                "role": "influent time-series input",
                "status": "PASS" if influent_ok else "FAIL",
                "checks": influent_checks,
            },
            input2: {
                "role": "initial digester state",
                "status": "PASS" if initial_ok else "FAIL",
                "checks": initial_checks,
            },
        },
    }

    # Emit the validation report to S3 before failing (if it fails) so the
    # outcome is always recorded.
    report_local = "validation_report_local.json"
    with open(report_local, "w") as f:
        json.dump(report, f, indent=2)
    faasr_put_file(local_file=report_local, remote_folder=folder, remote_file=output1)
    faasr_log(f"validate_inputs: wrote validation report to '{output1}' (overall {report['overall_status']})")

    if not overall_ok:
        raise ValueError(
            f"Input validation FAILED for the PyADM1 digester inputs. See '{output1}'. "
            f"'{input1}' status={report['files'][input1]['status']}, "
            f"'{input2}' status={report['files'][input2]['status']}."
        )

    faasr_log("validate_inputs: all input checks passed; inputs are safe for simulation")
