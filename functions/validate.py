import pandas as pd
import numpy as np

# Required ADM1 columns that must be present in the influent file
REQUIRED_INFLUENT_COLS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4",
    "X_pro", "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion", "Q", "T",
]

# Required columns that must be present in the initial-state file
REQUIRED_INITIAL_COLS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4",
    "X_pro", "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
]

T_MIN, T_MAX = 20.0, 60.0


def _row(column, check_type, status, details):
    return {"column": column, "check_type": check_type, "status": status, "details": str(details)}


def validate(folder: str, input1: str, input2: str, output1: str, output2: str) -> None:
    local_influent = "influent_interpolated.csv"
    local_initial = "initial.csv"
    local_report = "validation_report.csv"
    local_influent_out = "digester_influent.csv"

    faasr_get_file(local_file=local_influent, remote_folder=folder, remote_file=input1)
    faasr_log(f"validate: read {input1}")
    faasr_get_file(local_file=local_initial, remote_folder=folder, remote_file=input2)
    faasr_log(f"validate: read {input2}")

    influent = pd.read_csv(local_influent)
    initial = pd.read_csv(local_initial)

    rows = []

    # ── Influent checks ──────────────────────────────────────────────────────

    # (1) Required columns present
    missing_inf = [c for c in REQUIRED_INFLUENT_COLS if c not in influent.columns]
    rows.append(_row(
        "influent", "required_columns_present",
        "PASS" if not missing_inf else "FAIL",
        f"missing: {missing_inf}" if missing_inf else "all present",
    ))

    present_inf = [c for c in REQUIRED_INFLUENT_COLS if c in influent.columns]

    # (2) No missing values in required columns
    nan_counts = {c: int(influent[c].isna().sum()) for c in present_inf}
    any_nan = {c: v for c, v in nan_counts.items() if v > 0}
    rows.append(_row(
        "influent", "no_missing_values",
        "PASS" if not any_nan else "FAIL",
        f"NaN counts: {any_nan}" if any_nan else "no NaN in required columns",
    ))

    # (3) Non-negative numeric values in required columns
    numeric_inf = [c for c in present_inf if pd.api.types.is_numeric_dtype(influent[c])]
    neg_cols = {c: int((influent[c] < 0).sum()) for c in numeric_inf}
    neg_violations = {c: v for c, v in neg_cols.items() if v > 0}
    rows.append(_row(
        "influent", "non_negative_values",
        "PASS" if not neg_violations else "FAIL",
        f"negative counts: {neg_violations}" if neg_violations else "all non-negative",
    ))

    # (4) Temperature range
    if "T" in influent.columns:
        t_min = float(influent["T"].min())
        t_max = float(influent["T"].max())
        t_ok = (t_min >= T_MIN) and (t_max <= T_MAX)
        rows.append(_row(
            "T", "temperature_range_20_60_C",
            "PASS" if t_ok else "FAIL",
            f"min={t_min:.2f} max={t_max:.2f} (expected [{T_MIN}, {T_MAX}])",
        ))

    # (5) Flow Q is positive throughout
    if "Q" in influent.columns:
        n_nonpos = int((influent["Q"] <= 0).sum())
        rows.append(_row(
            "Q", "flow_positive",
            "PASS" if n_nonpos == 0 else "FAIL",
            f"{n_nonpos} non-positive values" if n_nonpos else "all positive",
        ))

    # ── Initial-state checks ─────────────────────────────────────────────────

    # (1) Required columns present
    missing_init = [c for c in REQUIRED_INITIAL_COLS if c not in initial.columns]
    rows.append(_row(
        "initial", "required_columns_present",
        "PASS" if not missing_init else "FAIL",
        f"missing: {missing_init}" if missing_init else "all present",
    ))

    present_init = [c for c in REQUIRED_INITIAL_COLS if c in initial.columns]

    # (2) No missing values
    nan_init = {c: int(initial[c].isna().sum()) for c in present_init}
    any_nan_init = {c: v for c, v in nan_init.items() if v > 0}
    rows.append(_row(
        "initial", "no_missing_values",
        "PASS" if not any_nan_init else "FAIL",
        f"NaN counts: {any_nan_init}" if any_nan_init else "no NaN in required columns",
    ))

    # (3) Non-negative values
    numeric_init = [c for c in present_init if pd.api.types.is_numeric_dtype(initial[c])]
    neg_init = {c: int((initial[c] < 0).sum()) for c in numeric_init}
    neg_init_viol = {c: v for c, v in neg_init.items() if v > 0}
    rows.append(_row(
        "initial", "non_negative_values",
        "PASS" if not neg_init_viol else "FAIL",
        f"negative counts: {neg_init_viol}" if neg_init_viol else "all non-negative",
    ))

    # ── Write outputs ────────────────────────────────────────────────────────

    report = pd.DataFrame(rows, columns=["column", "check_type", "status", "details"])
    report.to_csv(local_report, index=False)
    faasr_put_file(local_file=local_report, remote_folder=folder, remote_file=output1)
    faasr_log(f"validate: wrote {output1} ({len(rows)} checks, "
              f"{(report['status']=='PASS').sum()} passed, "
              f"{(report['status']=='FAIL').sum()} failed)")

    # Pass-through: validated influent renamed to the filename expected by pyadm1
    influent.to_csv(local_influent_out, index=False)
    faasr_put_file(local_file=local_influent_out, remote_folder=folder, remote_file=output2)
    faasr_log(f"validate: wrote {output2}")
