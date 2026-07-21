"""FaaSr step 5: validate.

Validate the cleaned influent file and the initial-state file that will feed
the PyADM1 simulation, and write a machine-readable validation_report.csv.

Checks performed:
  * required columns present in each file
  * no missing (NaN) values remain
  * concentrations are non-negative and finite
  * influent 'time' column is strictly increasing
  * initial-state file has exactly one row

The report has columns: file, check, status (PASS/FAIL/WARN), detail.
The step still succeeds (writes the report) even if checks fail, so the report
is always produced for inspection downstream.
"""

try:
    from FaaSr_py.client.py_client_stubs import faasr_get_file, faasr_put_file, faasr_log
except Exception:  # pragma: no cover
    pass

import numpy as np
import pandas as pd

INFLUENT_REQUIRED = [
    "time",
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
]

INITIAL_REQUIRED = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion",
    "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
]


def _check_required(rows, fname, df, required):
    missing = [c for c in required if c not in df.columns]
    status = "PASS" if not missing else "FAIL"
    detail = "all required columns present" if not missing else f"missing: {missing}"
    rows.append({"file": fname, "check": "required_columns", "status": status, "detail": detail})
    return missing


def _check_no_nan(rows, fname, df):
    n_nan = int(df.isna().sum().sum())
    status = "PASS" if n_nan == 0 else "FAIL"
    rows.append({"file": fname, "check": "no_missing_values", "status": status,
                 "detail": f"{n_nan} NaN cell(s)"})


def _check_non_negative(rows, fname, df, cols):
    cols = [c for c in cols if c in df.columns]
    numeric = df[cols].select_dtypes(include=[np.number])
    bad = []
    for c in numeric.columns:
        if not np.isfinite(numeric[c]).all():
            bad.append(f"{c}(non-finite)")
        elif (numeric[c] < 0).any():
            bad.append(f"{c}(negative)")
    status = "PASS" if not bad else "FAIL"
    detail = "all concentrations finite and >= 0" if not bad else f"problem cols: {bad}"
    rows.append({"file": fname, "check": "non_negative_finite", "status": status, "detail": detail})


def validate(folder, influent_file="digester_influent.csv",
             initial_file="digester_initial.csv",
             report_file="validation_report.csv"):
    faasr_log(f"validate: downloading {folder}/{influent_file} and {folder}/{initial_file}")
    faasr_get_file(remote_folder=folder, remote_file=influent_file,
                   local_folder=".", local_file="influent.csv")
    faasr_get_file(remote_folder=folder, remote_file=initial_file,
                   local_folder=".", local_file="initial.csv")

    influent = pd.read_csv("influent.csv")
    initial = pd.read_csv("initial.csv")

    rows = []

    # ---- Influent file ----
    _check_required(rows, influent_file, influent, INFLUENT_REQUIRED)
    _check_no_nan(rows, influent_file, influent)
    conc_cols = [c for c in INFLUENT_REQUIRED if c != "time"]
    _check_non_negative(rows, influent_file, influent, conc_cols)
    if "time" in influent.columns:
        incr = influent["time"].is_monotonic_increasing and influent["time"].is_unique
        rows.append({"file": influent_file, "check": "time_strictly_increasing",
                     "status": "PASS" if incr else "FAIL",
                     "detail": f"{len(influent)} rows"})

    # ---- Initial-state file ----
    _check_required(rows, initial_file, initial, INITIAL_REQUIRED)
    _check_no_nan(rows, initial_file, initial)
    _check_non_negative(rows, initial_file, initial, INITIAL_REQUIRED)
    rows.append({"file": initial_file, "check": "single_row",
                 "status": "PASS" if len(initial) == 1 else "FAIL",
                 "detail": f"{len(initial)} row(s)"})

    report = pd.DataFrame(rows, columns=["file", "check", "status", "detail"])
    report.to_csv(report_file, index=False)

    n_fail = int((report["status"] == "FAIL").sum())
    faasr_log(f"validate: {len(report)} checks, {n_fail} FAIL")
    faasr_put_file(local_folder=".", local_file=report_file,
                   remote_folder=folder, remote_file=report_file)
    faasr_log(f"validate: wrote {folder}/{report_file}")
