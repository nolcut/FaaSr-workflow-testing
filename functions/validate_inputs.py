import json
import os

import pandas as pd


# Columns required by the downstream PyADM1 simulation (functions/original_pyadm1.py).
# The influent file supplies the feed time-series read by setInfluent() plus the
# 'time' column used to drive the dynamic simulation loop.
INFLUENT_REQUIRED_COLUMNS = [
    "time",
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
]

# The initial-conditions file supplies the reactor state at t0 (row 0 of each column).
INITIAL_REQUIRED_COLUMNS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion",
    "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
]


def _validate_file(local_path, remote_name, required_columns):
    """Parse one PyADM1 input CSV and check it is well-formed. Returns a report dict."""
    report = {
        "file": remote_name,
        "status": "pass",
        "problems": [],
        "n_rows": 0,
        "n_columns": 0,
    }

    # Non-empty on disk.
    if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
        report["status"] = "fail"
        report["problems"].append("File is missing or empty (0 bytes).")
        return report

    # Parseable as CSV.
    try:
        df = pd.read_csv(local_path)
    except Exception as exc:
        report["status"] = "fail"
        report["problems"].append("File could not be parsed as CSV: %s" % exc)
        return report

    report["n_rows"] = int(df.shape[0])
    report["n_columns"] = int(df.shape[1])

    # Must contain at least one data row.
    if df.shape[0] == 0:
        report["status"] = "fail"
        report["problems"].append("File contains a header but no data rows.")

    # Required columns present.
    present = set(df.columns)
    missing = [c for c in required_columns if c not in present]
    if missing:
        report["status"] = "fail"
        report["problems"].append("Missing required column(s): %s" % ", ".join(missing))

    # For the columns that are present: numeric and non-null.
    for col in required_columns:
        if col not in present:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        n_bad = int(numeric.isna().sum())
        if n_bad > 0:
            report["status"] = "fail"
            report["problems"].append(
                "Column '%s' has %d non-numeric or missing value(s)." % (col, n_bad)
            )

    return report


def validate_inputs(folder: str, input1: str, input2: str, output1: str) -> None:
    faasr_log("validate_inputs: starting validation of '%s' and '%s' in folder '%s'"
              % (input1, input2, folder))

    # Download the two external input files from S3.
    influent_local = "digester_influent_input.csv"
    initial_local = "digester_initial_input.csv"

    faasr_log("Downloading influent file '%s'" % input1)
    faasr_get_file(local_file=influent_local, remote_folder=folder, remote_file=input1)

    faasr_log("Downloading initial-state file '%s'" % input2)
    faasr_get_file(local_file=initial_local, remote_folder=folder, remote_file=input2)

    # Validate each file against the columns the PyADM1 simulation requires.
    influent_report = _validate_file(influent_local, input1, INFLUENT_REQUIRED_COLUMNS)
    initial_report = _validate_file(initial_local, input2, INITIAL_REQUIRED_COLUMNS)

    overall_status = "pass"
    if influent_report["status"] != "pass" or initial_report["status"] != "pass":
        overall_status = "fail"

    validation_report = {
        "overall_status": overall_status,
        "folder": folder,
        "files": {
            input1: influent_report,
            input2: initial_report,
        },
    }

    # Write the validation report locally, then upload to S3.
    report_local = "validation_report.json"
    with open(report_local, "w") as f:
        json.dump(validation_report, f, indent=2)

    faasr_log("Validation report:\n%s" % json.dumps(validation_report, indent=2))
    faasr_put_file(local_file=report_local, remote_folder=folder, remote_file=output1)
    faasr_log("Uploaded validation report to '%s'" % output1)

    # Fail loudly so the downstream simulation does not run on bad inputs.
    if overall_status != "pass":
        problems = []
        for rep in (influent_report, initial_report):
            for p in rep["problems"]:
                problems.append("%s: %s" % (rep["file"], p))
        message = "Input validation FAILED. Problems: %s" % " | ".join(problems)
        faasr_log(message)
        raise ValueError(message)

    faasr_log("Input validation PASSED for both files.")
