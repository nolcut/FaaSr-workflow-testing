import pandas as pd
import numpy as np
import tempfile
import os

# Expected ADM1 influent columns (beyond time)
_INFLUENT_REQUIRED = [
    "Q", "T_ad",
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I", "S_cation", "S_anion",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa",
    "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
]

# Expected ADM1 initial-state columns (one data row, no time column)
_INITIAL_REQUIRED = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa",
    "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion",
    "S_hco3_ion", "S_co2", "S_nh3", "S_nh4_ion",
    "S_gas_h2", "S_gas_ch4", "S_gas_co2",
]


def _check(name, condition, pass_msg, fail_msg):
    status = "PASS" if condition else "FAIL"
    details = pass_msg if condition else fail_msg
    return {"check": name, "status": status, "details": details}


def validate(folder: str, input1: str, input2: str, output1: str) -> None:
    faasr_log("validate: starting")

    with tempfile.TemporaryDirectory() as tmp:
        local_inf = os.path.join(tmp, "influent.csv")
        local_ini = os.path.join(tmp, "initial.csv")
        local_out = os.path.join(tmp, "report.csv")

        faasr_get_file(local_file=local_inf, remote_folder=folder, remote_file=input1)
        faasr_get_file(local_file=local_ini, remote_folder=folder, remote_file=input2)

        inf = pd.read_csv(local_inf)
        ini = pd.read_csv(local_ini)
        faasr_log(f"validate: influent {inf.shape}, initial {ini.shape}")

        rows = []

        # ── Influent checks ─────────────────────────────────────────────────

        # 1. Required columns present
        missing_inf = [c for c in _INFLUENT_REQUIRED if c not in inf.columns]
        rows.append(_check(
            "influent_required_columns",
            len(missing_inf) == 0,
            f"All {len(_INFLUENT_REQUIRED)} required columns present",
            f"Missing columns: {missing_inf}",
        ))

        # 2. Numeric dtypes for all non-time columns
        non_numeric_inf = [
            c for c in inf.columns
            if c != "time" and not pd.api.types.is_numeric_dtype(inf[c])
        ]
        rows.append(_check(
            "influent_numeric_dtypes",
            len(non_numeric_inf) == 0,
            "All non-time columns are numeric",
            f"Non-numeric columns: {non_numeric_inf}",
        ))

        # 3. No missing values in required columns
        inf_key_cols = [c for c in _INFLUENT_REQUIRED if c in inf.columns]
        nan_counts = inf[inf_key_cols].isna().sum()
        nan_cols = nan_counts[nan_counts > 0].to_dict()
        rows.append(_check(
            "influent_no_missing_values",
            len(nan_cols) == 0,
            "No missing values in required columns",
            f"Columns with NaN: {nan_cols}",
        ))

        # 4. Non-negative values in numeric columns
        numeric_inf = inf.select_dtypes(include=[np.number])
        neg_cols_inf = {
            c: int((numeric_inf[c] < 0).sum())
            for c in numeric_inf.columns
            if (numeric_inf[c] < 0).any()
        }
        rows.append(_check(
            "influent_non_negative_values",
            len(neg_cols_inf) == 0,
            "All numeric columns are non-negative",
            f"Columns with negative values (count): {neg_cols_inf}",
        ))

        # 5. Row count sanity (must have at least one row)
        rows.append(_check(
            "influent_row_count",
            len(inf) > 0,
            f"{len(inf)} rows present",
            "Influent file is empty",
        ))

        # 6. Time column present and monotonically increasing
        if "time" in inf.columns:
            mono = bool(inf["time"].is_monotonic_increasing)
            rows.append(_check(
                "influent_time_monotonic",
                mono,
                "time column is monotonically increasing",
                "time column is NOT monotonically increasing",
            ))
        else:
            rows.append({"check": "influent_time_monotonic", "status": "FAIL",
                         "details": "time column absent"})

        # 7. Time step consistency (15-min = 1/96 day, allow 1% tolerance)
        if "time" in inf.columns and len(inf) > 1:
            diffs = inf["time"].diff().dropna()
            expected_step = 1.0 / 96.0
            step_ok = bool((diffs - expected_step).abs().max() <= expected_step * 0.01)
            rows.append(_check(
                "influent_15min_timestep",
                step_ok,
                f"Uniform 15-min timestep (step={expected_step:.6f} days)",
                f"Irregular timestep detected; min={diffs.min():.6f} max={diffs.max():.6f}",
            ))

        # ── Initial-state checks ─────────────────────────────────────────────

        # 8. Required columns present
        missing_ini = [c for c in _INITIAL_REQUIRED if c not in ini.columns]
        rows.append(_check(
            "initial_required_columns",
            len(missing_ini) == 0,
            f"All {len(_INITIAL_REQUIRED)} required columns present",
            f"Missing columns: {missing_ini}",
        ))

        # 9. Exactly one data row
        rows.append(_check(
            "initial_single_row",
            len(ini) == 1,
            "Initial-state file contains exactly 1 data row",
            f"Expected 1 row, found {len(ini)}",
        ))

        # 10. Numeric dtypes
        non_numeric_ini = [
            c for c in ini.columns
            if not pd.api.types.is_numeric_dtype(ini[c])
        ]
        rows.append(_check(
            "initial_numeric_dtypes",
            len(non_numeric_ini) == 0,
            "All columns are numeric",
            f"Non-numeric columns: {non_numeric_ini}",
        ))

        # 11. No missing values
        nan_ini = ini.isna().sum()
        nan_ini_cols = nan_ini[nan_ini > 0].to_dict()
        rows.append(_check(
            "initial_no_missing_values",
            len(nan_ini_cols) == 0,
            "No missing values",
            f"Columns with NaN: {nan_ini_cols}",
        ))

        # 12. Non-negative values
        numeric_ini = ini.select_dtypes(include=[np.number])
        neg_cols_ini = {
            c: int((numeric_ini[c] < 0).sum())
            for c in numeric_ini.columns
            if (numeric_ini[c] < 0).any()
        }
        rows.append(_check(
            "initial_non_negative_values",
            len(neg_cols_ini) == 0,
            "All numeric columns are non-negative",
            f"Columns with negative values (count): {neg_cols_ini}",
        ))

        # ── Write report ─────────────────────────────────────────────────────
        report = pd.DataFrame(rows, columns=["check", "status", "details"])
        n_pass = (report["status"] == "PASS").sum()
        n_fail = (report["status"] == "FAIL").sum()
        faasr_log(f"validate: {n_pass} PASS, {n_fail} FAIL")

        report.to_csv(local_out, index=False)
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
        faasr_log("validate: done")
