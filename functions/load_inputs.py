import os
import tempfile
import pandas as pd
import numpy as np


# Required ADM1 state variable columns for the influent feed CSV.
# These are the 26 core ADM1 soluble/particulate state variables plus
# ion/gas derived quantities observed in the reference data.  The `time`,
# `Q`, and `T (C)` meta-columns are handled separately.
INFLUENT_STATE_VARS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac",
    "S_h2", "S_ch4", "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li",
    "X_su", "X_aa", "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
]

# Required columns for the initial conditions CSV (38 columns total —
# 26 core + 12 derived ion/gas variables).
INITIAL_STATE_VARS = [
    "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac",
    "S_h2", "S_ch4", "S_IC", "S_IN", "S_I",
    "X_xc", "X_ch", "X_pr", "X_li",
    "X_su", "X_aa", "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I",
    "S_cation", "S_anion",
    "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion",
    "S_hco3_ion", "S_co2", "S_nh3", "S_nh4_ion",
    "S_gas_h2", "S_gas_ch4", "S_gas_co2",
]


def _validate_dataframe(df: pd.DataFrame, required_cols: list, label: str) -> pd.DataFrame:
    """Validate a loaded ADM1 CSV DataFrame.

    Checks:
      1. All required ADM1 state variable columns are present.
      2. All numeric values are non-negative and finite.

    Raises ValueError on any violation so the caller (and FaaSr) fail loudly.
    Returns the DataFrame unchanged when validation passes.
    """
    # --- 1. Column presence check -----------------------------------------
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"{label}: missing required ADM1 columns: {missing}"
        )

    # --- 2. Numeric validity: non-negative and finite ----------------------
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_df = df[numeric_cols]

    # Check for NaN / Inf
    bad_finite = numeric_df.columns[numeric_df.apply(lambda c: (~np.isfinite(c)).any())].tolist()
    if bad_finite:
        raise ValueError(
            f"{label}: columns contain NaN or infinite values: {bad_finite}"
        )

    # Check for negative values (state variables must be ≥ 0)
    bad_neg = numeric_df.columns[numeric_df.apply(lambda c: (c < 0).any())].tolist()
    if bad_neg:
        raise ValueError(
            f"{label}: columns contain negative values: {bad_neg}"
        )

    return df


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "digester_influent.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Digester influent CSV must be present in S3 before load_inputs can download and validate it")
        raise SystemExit(1)
    if "digester_initial.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Digester initial conditions CSV must be present in S3 before load_inputs can download and validate it")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "validated_influent.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Validated influent CSV should have been uploaded to S3 after successful validation and re-upload")
        raise SystemExit(1)
    if "validated_initial.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Validated initial conditions CSV should have been uploaded to S3 after successful validation and re-upload")
        raise SystemExit(1)
# --- end contract helpers ---


def load_inputs(folder: str, input1: str, input2: str, output1: str, output2: str) -> None:
    """Download, validate, and re-upload the ADM1 influent and initial-conditions CSVs.

    Parameters
    ----------
    folder  : S3 folder (remote_folder for FaaSr calls)
    input1  : remote filename of the digester influent CSV
    input2  : remote filename of the digester initial conditions CSV
    output1 : remote filename for the validated influent CSV
    output2 : remote filename for the validated initial conditions CSV
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    with tempfile.TemporaryDirectory() as tmpdir:
        local_influent  = os.path.join(tmpdir, "influent.csv")
        local_initial   = os.path.join(tmpdir, "initial.csv")
        local_val_inf   = os.path.join(tmpdir, "validated_influent.csv")
        local_val_init  = os.path.join(tmpdir, "validated_initial.csv")

        # ------------------------------------------------------------------
        # 1. Download inputs from S3
        # ------------------------------------------------------------------
        faasr_log(f"Downloading influent file '{input1}' from folder '{folder}'")
        faasr_get_file(local_file=local_influent, remote_folder=folder, remote_file=input1)

        faasr_log(f"Downloading initial conditions file '{input2}' from folder '{folder}'")
        faasr_get_file(local_file=local_initial, remote_folder=folder, remote_file=input2)

        # ------------------------------------------------------------------
        # 2. Parse CSVs
        # ------------------------------------------------------------------
        faasr_log("Parsing influent CSV")
        try:
            df_influent = pd.read_csv(local_influent)
        except Exception as e:
            faasr_log(f"ERROR: failed to parse influent CSV '{input1}': {e}")
            raise

        faasr_log("Parsing initial conditions CSV")
        try:
            df_initial = pd.read_csv(local_initial)
        except Exception as e:
            faasr_log(f"ERROR: failed to parse initial conditions CSV '{input2}': {e}")
            raise

        # ------------------------------------------------------------------
        # 3. Log data summaries
        # ------------------------------------------------------------------
        faasr_log(
            f"Influent CSV loaded: shape={df_influent.shape}, "
            f"columns={df_influent.columns.tolist()}"
        )
        faasr_log(
            f"Influent basic statistics:\n{df_influent.describe().to_string()}"
        )

        faasr_log(
            f"Initial conditions CSV loaded: shape={df_initial.shape}, "
            f"columns={df_initial.columns.tolist()}"
        )
        faasr_log(
            f"Initial conditions basic statistics:\n{df_initial.describe().to_string()}"
        )

        # ------------------------------------------------------------------
        # 4. Validate
        # ------------------------------------------------------------------
        faasr_log("Validating influent CSV")
        try:
            df_influent = _validate_dataframe(df_influent, INFLUENT_STATE_VARS, "influent")
        except ValueError as e:
            faasr_log(f"ERROR: influent validation failed: {e}")
            raise

        faasr_log("Influent CSV passed validation")

        faasr_log("Validating initial conditions CSV")
        try:
            df_initial = _validate_dataframe(df_initial, INITIAL_STATE_VARS, "initial conditions")
        except ValueError as e:
            faasr_log(f"ERROR: initial conditions validation failed: {e}")
            raise

        faasr_log("Initial conditions CSV passed validation")

        # ------------------------------------------------------------------
        # 5. Write validated CSVs to local temp files
        # ------------------------------------------------------------------
        df_influent.to_csv(local_val_inf, index=False)
        df_initial.to_csv(local_val_init, index=False)

        # ------------------------------------------------------------------
        # 6. Upload validated outputs to S3
        # ------------------------------------------------------------------
        faasr_log(f"Uploading validated influent CSV as '{output1}' to folder '{folder}'")
        faasr_put_file(local_file=local_val_inf, remote_folder=folder, remote_file=output1)

        faasr_log(f"Uploading validated initial conditions CSV as '{output2}' to folder '{folder}'")
        faasr_put_file(local_file=local_val_init, remote_folder=folder, remote_file=output2)

        faasr_log("load_inputs complete: both validated files uploaded successfully")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---