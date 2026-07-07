import json
import os

import pandas as pd

# Columns the PyADM1 simulation (context/00_pyadm1.py) reads from each CSV.
# These MUST match the exact names indexed in setInfluent(...) / initial_state[...].
_INFLUENT_STATE_COLUMNS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I", "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
    "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I", "S_cation", "S_anion",
]
# The simulation also does `t = influent_state['time']`, so 'time' is required.
_INFLUENT_REQUIRED_COLUMNS = ["time"] + _INFLUENT_STATE_COLUMNS

# initial_state additionally supplies the reactor's initial ion/gas states.
_INITIAL_REQUIRED_COLUMNS = _INFLUENT_STATE_COLUMNS + [
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion",
    "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
]

# Columns that represent concentrations / flows and must be non-negative.
# (Every state variable in ADM1 is a non-negative concentration.)
_NONNEGATIVE_EXEMPT = set()  # cations/anions are still non-negative concentrations here


def _validate_csv(local_path, file_label, required_columns, *, is_influent):
    """Validate one digester CSV. Returns a report dict. Raises ValueError on failure."""
    if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
        msg = f"Validation failed for {file_label}: file is missing or empty."
        faasr_log(msg)
        raise ValueError(msg)

    try:
        df = pd.read_csv(local_path)
    except Exception as exc:
        msg = f"Validation failed for {file_label}: could not parse CSV ({exc})."
        faasr_log(msg)
        raise ValueError(msg)

    report = {
        "file": file_label,
        "n_rows": int(len(df)),
        "columns_checked": list(required_columns),
        "checks": [],
    }

    # --- Required columns present ---
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        msg = (
            f"Validation failed for {file_label}: missing required column(s): "
            f"{', '.join(missing)}."
        )
        faasr_log(msg)
        raise ValueError(msg)
    report["checks"].append("all required columns present")

    if len(df) == 0:
        msg = f"Validation failed for {file_label}: contains no data rows."
        faasr_log(msg)
        raise ValueError(msg)

    # For the initial-state file, PyADM1 reads only row 0 but it must exist.
    if not is_influent and len(df) < 1:
        msg = f"Validation failed for {file_label}: initial state requires at least one row."
        faasr_log(msg)
        raise ValueError(msg)

    # --- Numeric type check for every required column ---
    for col in required_columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        bad_mask = coerced.isna() & df[col].notna()
        if bad_mask.any() or coerced.isna().any():
            bad_idx = df.index[coerced.isna()].tolist()
            msg = (
                f"Validation failed for {file_label}: column '{col}' contains "
                f"non-numeric or missing values at row(s) {bad_idx[:10]}."
            )
            faasr_log(msg)
            raise ValueError(msg)
    report["checks"].append("all columns parse as numeric with no missing values")

    # --- Physical range checks ---
    # Concentration / state columns must be non-negative.
    for col in _INFLUENT_STATE_COLUMNS:
        vals = pd.to_numeric(df[col])
        neg_idx = df.index[vals < 0].tolist()
        if neg_idx:
            msg = (
                f"Validation failed for {file_label}: column '{col}' has negative "
                f"value(s) at row(s) {neg_idx[:10]} (concentrations must be non-negative)."
            )
            faasr_log(msg)
            raise ValueError(msg)
    report["checks"].append("all concentration columns non-negative")

    if is_influent:
        # 'time' must be non-negative and strictly increasing (a valid time series).
        t = pd.to_numeric(df["time"])
        if (t < 0).any():
            msg = f"Validation failed for {file_label}: 'time' column has negative value(s)."
            faasr_log(msg)
            raise ValueError(msg)
        diffs = t.diff().dropna()
        if (diffs <= 0).any():
            msg = (
                f"Validation failed for {file_label}: 'time' column must be strictly "
                f"increasing."
            )
            faasr_log(msg)
            raise ValueError(msg)
        report["checks"].append("'time' non-negative and strictly increasing")
    else:
        # Initial-state ion/gas columns must be non-negative too.
        for col in ("S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion",
                    "S_hco3_ion", "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2"):
            vals = pd.to_numeric(df[col])
            neg_idx = df.index[vals < 0].tolist()
            if neg_idx:
                msg = (
                    f"Validation failed for {file_label}: column '{col}' has negative "
                    f"value(s) at row(s) {neg_idx[:10]}."
                )
                faasr_log(msg)
                raise ValueError(msg)
        # S_H_ion must be strictly positive so pH = -log10(S_H_ion) is defined & plausible.
        s_h = pd.to_numeric(df["S_H_ion"])
        if (s_h <= 0).any():
            msg = (
                f"Validation failed for {file_label}: 'S_H_ion' must be strictly positive "
                f"to compute a valid pH."
            )
            faasr_log(msg)
            raise ValueError(msg)
        import math
        ph0 = -math.log10(float(s_h.iloc[0]))
        if not (0.0 <= ph0 <= 14.0):
            msg = (
                f"Validation failed for {file_label}: derived initial pH {ph0:.3f} is "
                f"outside the plausible range 0-14."
            )
            faasr_log(msg)
            raise ValueError(msg)
        report["checks"].append("ion/gas columns non-negative; derived pH within 0-14")
        report["derived_initial_pH"] = round(ph0, 4)

    report["passed"] = True
    faasr_log(f"Validation passed for {file_label} ({report['n_rows']} rows).")
    return report


def validate_inputs(folder: str, input1: str, input2: str, output1: str) -> None:
    faasr_log(f"Starting validate_inputs for '{input1}' and '{input2}' in folder '{folder}'.")

    local_influent = "digester_influent_local.csv"
    local_initial = "digester_initial_local.csv"

    # --- Fetch the two external input CSVs from S3 ---
    faasr_get_file(local_file=local_influent, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_initial, remote_folder=folder, remote_file=input2)

    # --- Validate each file (raises loudly on any failure) ---
    influent_report = _validate_csv(
        local_influent, input1, _INFLUENT_REQUIRED_COLUMNS, is_influent=True
    )
    initial_report = _validate_csv(
        local_initial, input2, _INITIAL_REQUIRED_COLUMNS, is_influent=False
    )

    report = {
        "workflow": "digester_pyadm1_pipeline",
        "step": "validate_inputs",
        "status": "passed",
        "files": [influent_report, initial_report],
        "summary": (
            f"Both input files passed all validation checks: "
            f"{input1} ({influent_report['n_rows']} rows) and "
            f"{input2} ({initial_report['n_rows']} rows)."
        ),
    }

    local_report = "validation_report_local.json"
    with open(local_report, "w") as fh:
        json.dump(report, fh, indent=2)

    faasr_put_file(local_file=local_report, remote_folder=folder, remote_file=output1)
    faasr_log(f"Validation report written to '{output1}'. All checks passed.")
