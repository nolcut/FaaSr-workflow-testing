import os
import pandas as pd


# --- ADM1 / BSM2 required column definitions -------------------------------
# These are the exact column names consumed by the downstream PyADM1 simulation
# (see the ADM1 setInfluent() / initial-state assignments). They MUST all be
# present in the corresponding input files or the simulation cannot run.

# Influent time-series file: a leading time column plus the 26 ADM1 input
# (feed) state variables read via influent_state[<col>][i].
INFLUENT_STATE_COLS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
    "S_IC", "S_IN", "S_I", "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
    "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I", "S_cation", "S_anion",
]
INFLUENT_REQUIRED_COLS = ["time"] + INFLUENT_STATE_COLS

# Initial reactor-state file: the 26 base state variables plus the ion / gas
# phase state variables read via initial_state[<col>][0].
INITIAL_REQUIRED_COLS = INFLUENT_STATE_COLS + [
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion",
    "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
]


def validate_inputs(folder: str, input1: str, input2: str, output1: str) -> None:
    faasr_log("validate_inputs: starting validation of PyADM1 digester inputs")

    influent_local = "digester_influent.csv"
    initial_local = "digester_initial.csv"

    faasr_get_file(local_file=influent_local, remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file=initial_local, remote_folder=folder, remote_file=input2)

    # Each entry: (file_label, check_name, status, details)
    report_rows = []

    def record(file_label, check_name, ok, details=""):
        status = "PASS" if ok else "FAIL"
        report_rows.append(
            {"file": file_label, "check": check_name, "status": status, "details": details}
        )
        faasr_log(f"[{status}] {file_label} :: {check_name} :: {details}")
        return ok

    def validate_file(file_label, local_path, remote_name, required_cols, require_time):
        # --- readability -----------------------------------------------------
        if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
            record(file_label, "file_present_and_nonempty", False,
                   f"'{remote_name}' is missing or empty after download")
            return
        record(file_label, "file_present_and_nonempty", True,
               f"'{remote_name}' downloaded ({os.path.getsize(local_path)} bytes)")

        try:
            df = pd.read_csv(local_path)
        except Exception as exc:  # malformed CSV — a genuine defect, not fabricated
            record(file_label, "csv_parseable", False, f"failed to parse CSV: {exc}")
            return
        record(file_label, "csv_parseable", True, f"parsed shape={df.shape}")

        # --- non-empty rows --------------------------------------------------
        record(file_label, "has_rows", len(df) > 0,
               f"row count = {len(df)}")

        # --- required columns present ---------------------------------------
        missing = [c for c in required_cols if c not in df.columns]
        record(file_label, "required_columns_present", len(missing) == 0,
               "all required columns present" if not missing
               else f"missing columns: {missing}")

        # Columns available for numeric checks (only those that exist).
        present_cols = [c for c in required_cols if c in df.columns]

        # --- numeric values --------------------------------------------------
        non_numeric = []
        for col in present_cols:
            coerced = pd.to_numeric(df[col], errors="coerce")
            # A value is non-numeric if coercion produced NaN where the source
            # was not itself an empty/NaN entry (empty entries handled below).
            introduced = coerced.isna() & df[col].notna()
            if introduced.any():
                non_numeric.append(col)
        record(file_label, "all_values_numeric", len(non_numeric) == 0,
               "all required columns numeric" if not non_numeric
               else f"non-numeric values in columns: {non_numeric}")

        # --- no missing entries ---------------------------------------------
        cols_with_na = [c for c in present_cols
                        if pd.to_numeric(df[c], errors="coerce").isna().any()]
        record(file_label, "no_missing_values", len(cols_with_na) == 0,
               "no missing entries in required columns" if not cols_with_na
               else f"missing/NaN entries in columns: {cols_with_na}")

        # --- non-negative concentrations ------------------------------------
        # 'time' is not a concentration; every ADM1 state variable is a
        # concentration and must be >= 0.
        conc_cols = [c for c in present_cols if c != "time"]
        negative_cols = []
        for col in conc_cols:
            vals = pd.to_numeric(df[col], errors="coerce")
            if (vals < 0).any():
                negative_cols.append(col)
        record(file_label, "non_negative_concentrations", len(negative_cols) == 0,
               "all concentrations non-negative" if not negative_cols
               else f"negative values in columns: {negative_cols}")

        # --- time column checks (influent only) -----------------------------
        if require_time:
            if "time" not in df.columns:
                record(file_label, "time_column_present", False,
                       "influent file has no 'time' column")
            else:
                record(file_label, "time_column_present", True, "'time' column present")
                time_vals = pd.to_numeric(df["time"], errors="coerce")
                if time_vals.isna().any():
                    record(file_label, "time_ordered", False,
                           "'time' column contains non-numeric/missing entries")
                else:
                    ordered = time_vals.is_monotonic_increasing
                    strictly = (time_vals.diff().dropna() > 0).all()
                    record(file_label, "time_ordered", bool(ordered),
                           "'time' is monotonically increasing" if ordered
                           else "'time' is not in increasing order")
                    record(file_label, "time_strictly_increasing", bool(strictly),
                           "'time' strictly increasing (no duplicates)" if strictly
                           else "'time' has duplicate or non-increasing steps")

    validate_file("digester_influent.csv", influent_local, input1,
                  INFLUENT_REQUIRED_COLS, require_time=True)
    validate_file("digester_initial.csv", initial_local, input2,
                  INITIAL_REQUIRED_COLS, require_time=False)

    # --- assemble and upload the report -------------------------------------
    report_df = pd.DataFrame(report_rows, columns=["file", "check", "status", "details"])
    report_local = "validation_report.csv"
    report_df.to_csv(report_local, index=False)
    faasr_put_file(local_file=report_local, remote_folder=folder, remote_file=output1)
    faasr_log(f"validate_inputs: wrote validation report '{output1}' with {len(report_df)} checks")

    failures = report_df[report_df["status"] == "FAIL"]
    if len(failures) > 0:
        summary = "; ".join(
            f"{r.file}/{r.check}: {r.details}" for r in failures.itertuples(index=False)
        )
        msg = f"Input validation FAILED with {len(failures)} issue(s): {summary}"
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log("validate_inputs: all checks passed — inputs are valid for PyADM1 simulation")
