def validate(folder: str, input1: str, input2: str, output1: str) -> None:
    import pandas as pd
    import numpy as np
    import tempfile, os

    # Required ADM1 influent columns (Q + T + 26 lab state variables)
    REQUIRED_INFLUENT_COLS = [
        "Q", "T (F)",
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
        "S_IC", "S_IN", "S_I",
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa",
        "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
        "S_cation", "S_anion",
    ]
    # Concentration columns that must be >= 0
    CONC_COLS = [c for c in REQUIRED_INFLUENT_COLS if c not in ("Q", "T (F)")]

    local_inf = tempfile.mktemp(suffix=".csv")
    local_ini = tempfile.mktemp(suffix=".csv")
    local_out = tempfile.mktemp(suffix=".csv")

    faasr_get_file(local_file=local_inf, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=local_ini, remote_folder=folder, remote_file=input2)
    faasr_log(f"validate: read {input1} and {input2} from {folder}")

    inf = pd.read_csv(local_inf)
    ini = pd.read_csv(local_ini)

    rows = []

    def _row(check_name, file, status, column, n_violations, obs_min, obs_max, details):
        return {
            "check_name": check_name,
            "file": file,
            "status": status,
            "column": column,
            "n_violations": n_violations,
            "observed_min": obs_min,
            "observed_max": obs_max,
            "details": details,
        }

    # ── INFLUENT CHECKS ────────────────────────────────────────────────────────

    # 1. Required columns present
    missing_cols = [c for c in REQUIRED_INFLUENT_COLS if c not in inf.columns]
    rows.append(_row(
        "required_columns", input1,
        "PASS" if not missing_cols else "FAIL",
        "",
        len(missing_cols),
        "", "",
        f"missing: {missing_cols}" if missing_cols else "all required columns present",
    ))

    # 2. NaN / missing values per column
    for col in inf.columns:
        n = int(inf[col].isna().sum())
        rows.append(_row(
            "no_missing_values", input1,
            "PASS" if n == 0 else "FAIL",
            col, n,
            "", "",
            f"{n} NaN(s)" if n else "no missing values",
        ))

    # 3. Physical plausibility — only check cols that are present
    present = set(inf.columns)

    # Q > 0
    if "Q" in present:
        col_vals = inf["Q"].dropna()
        n_viol = int((col_vals <= 0).sum())
        rows.append(_row(
            "Q_positive", input1,
            "PASS" if n_viol == 0 else "FAIL",
            "Q", n_viol,
            float(col_vals.min()), float(col_vals.max()),
            f"{n_viol} rows with Q <= 0" if n_viol else "all Q > 0",
        ))

    # T in 0–60 °C  (column still named "T (F)" but values are in Celsius after convert_units)
    if "T (F)" in present:
        col_vals = inf["T (F)"].dropna()
        n_viol = int(((col_vals < 0) | (col_vals > 60)).sum())
        rows.append(_row(
            "T_range_0_60C", input1,
            "PASS" if n_viol == 0 else "FAIL",
            "T (F)", n_viol,
            float(col_vals.min()), float(col_vals.max()),
            f"{n_viol} rows outside 0–60 °C" if n_viol else "all T in 0–60 °C",
        ))

    # Concentrations >= 0
    for col in CONC_COLS:
        if col not in present:
            continue
        col_vals = inf[col].dropna()
        n_viol = int((col_vals < 0).sum())
        rows.append(_row(
            "concentration_nonnegative", input1,
            "PASS" if n_viol == 0 else "FAIL",
            col, n_viol,
            float(col_vals.min()), float(col_vals.max()),
            f"{n_viol} negative values" if n_viol else "all values >= 0",
        ))

    # ── INITIAL-STATE CHECKS ───────────────────────────────────────────────────

    # 1. Structure: expect exactly 1 data row and the known ADM1 state columns
    EXPECTED_INITIAL_COLS = [
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
        "S_IC", "S_IN", "S_I",
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa",
        "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
        "S_cation", "S_anion",
        "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion",
        "S_hco3_ion", "S_co2", "S_nh3", "S_nh4_ion",
        "S_gas_h2", "S_gas_ch4", "S_gas_co2",
    ]
    missing_ini = [c for c in EXPECTED_INITIAL_COLS if c not in ini.columns]
    n_rows_ini = len(ini)
    struct_ok = (not missing_ini) and (n_rows_ini == 1)
    rows.append(_row(
        "initial_structure", input2,
        "PASS" if struct_ok else "FAIL",
        "",
        len(missing_ini),
        "", "",
        (f"rows={n_rows_ini}, missing cols={missing_ini}"
         if not struct_ok else f"1 row, {len(ini.columns)} columns"),
    ))

    # 2. No missing values
    n_nan_ini = int(ini.isna().sum().sum())
    rows.append(_row(
        "initial_no_missing", input2,
        "PASS" if n_nan_ini == 0 else "FAIL",
        "", n_nan_ini, "", "",
        f"{n_nan_ini} NaN(s)" if n_nan_ini else "no missing values",
    ))

    # 3. All numeric values non-negative
    num_ini = ini.select_dtypes(include=[np.number])
    n_neg_ini = int((num_ini < 0).sum().sum())
    if len(num_ini.columns):
        rows.append(_row(
            "initial_nonnegative", input2,
            "PASS" if n_neg_ini == 0 else "FAIL",
            "", n_neg_ini,
            float(num_ini.min().min()), float(num_ini.max().max()),
            f"{n_neg_ini} negative value(s)" if n_neg_ini else "all values >= 0",
        ))

    # ── WRITE REPORT ──────────────────────────────────────────────────────────

    report = pd.DataFrame(rows)
    report.to_csv(local_out, index=False)

    n_fail = int((report["status"] == "FAIL").sum())
    faasr_log(f"validate: {len(report)} checks, {n_fail} FAIL(s)")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    os.remove(local_inf)
    os.remove(local_ini)
    os.remove(local_out)
    faasr_log("validate: done")
