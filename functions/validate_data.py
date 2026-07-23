import pandas as pd
import numpy as np

# 26 ADM1 state variables that must be present in the cleaned influent.
STATE_COLUMNS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
    "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
]

# The initial-state file additionally carries the ion / gas-phase states.
INITIAL_EXTRA = [
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion",
    "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
]


def validate_data(folder="PyADM1-orig",
                  influent_file="digester_influent.csv",
                  initial_file="digester_initial.csv",
                  report_file="validation_report.csv"):
    """Step 5 - validate the cleaned influent and the initial-state files and
    write validation_report.csv."""
    faasr_get_file(remote_folder=folder, remote_file=influent_file, local_file="influent.csv")
    faasr_get_file(remote_folder=folder, remote_file=initial_file, local_file="initial.csv")

    inf = pd.read_csv("influent.csv")
    init = pd.read_csv("initial.csv")

    checks = []  # (check, target, status, detail)

    def add(check, target, ok, detail):
        checks.append({"check": check, "target": target,
                       "status": "PASS" if ok else "FAIL", "detail": detail})

    # --- Influent: time column present and strictly increasing ---
    has_time = "time" in inf.columns
    add("time column present", influent_file, has_time,
        "found" if has_time else "missing 'time' column")
    if has_time:
        t = pd.to_numeric(inf["time"], errors="coerce")
        mono = bool(t.is_monotonic_increasing) and bool(t.notna().all())
        add("time strictly increasing", influent_file, mono,
            "monotonic increasing" if mono else "time not monotonic / has NaN")

    # --- Influent: required state columns present ---
    missing = [c for c in STATE_COLUMNS if c not in inf.columns]
    add("all 26 state columns present", influent_file, len(missing) == 0,
        "all present" if not missing else f"missing: {missing}")

    # --- Influent: no NaNs in state columns ---
    present = [c for c in STATE_COLUMNS if c in inf.columns]
    n_nan = int(inf[present].isna().sum().sum()) if present else -1
    add("no missing values in state columns", influent_file, n_nan == 0,
        f"{n_nan} NaN value(s)")

    # --- Influent: physical non-negativity (COD / concentrations >= 0) ---
    neg_cols = [c for c in present if (inf[c].astype(float) < 0).any()]
    add("non-negative concentrations", influent_file, len(neg_cols) == 0,
        "all >= 0" if not neg_cols else f"negative values in: {neg_cols}")

    add("influent row count > 0", influent_file, len(inf) > 0, f"{len(inf)} rows")

    # --- Initial state: single row and required columns ---
    add("initial file has exactly one row", initial_file, len(init) == 1,
        f"{len(init)} row(s)")
    init_missing = [c for c in STATE_COLUMNS + INITIAL_EXTRA if c not in init.columns]
    add("initial state columns present", initial_file, len(init_missing) == 0,
        "all present" if not init_missing else f"missing: {init_missing}")
    init_present = [c for c in STATE_COLUMNS + INITIAL_EXTRA if c in init.columns]
    init_nan = int(init[init_present].isna().sum().sum()) if init_present else -1
    add("no missing values in initial state", initial_file, init_nan == 0,
        f"{init_nan} NaN value(s)")

    report = pd.DataFrame(checks, columns=["check", "target", "status", "detail"])
    report.to_csv("validation_report.csv", index=False)
    faasr_put_file(local_file="validation_report.csv", remote_folder=folder, remote_file=report_file)

    n_fail = int((report["status"] == "FAIL").sum())
    faasr_log(f"validate_data: {len(report)} checks, {n_fail} failure(s); "
              f"wrote {folder}/{report_file}")
    if n_fail:
        faasr_log("validate_data WARNING: validation failures detected -> "
                  + "; ".join(report.loc[report["status"] == "FAIL", "check"].tolist()))
