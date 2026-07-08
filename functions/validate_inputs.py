import pandas as pd
import numpy as np


def validate_inputs(input_folder="pyadm1-inputs",
                    influent_file="digester_influent.csv",
                    initial_file="digester_initial.csv"):
    """
    FaaSr stage 1 of 3.

    Downloads the two PyADM1 input CSVs from S3, validates that they contain
    every column the PyADM1 model reads and that all values are present,
    numeric and physically plausible (finite, non-negative).  On success the
    validated files are re-uploaded to a clean 'validated' prefix so the
    downstream simulation reads from a known-good location.  Any problem raises
    an exception, which aborts the FaaSr workflow before the (expensive)
    simulation runs.
    """

    # --- columns the PyADM1 model actually reads -------------------------
    # influent_state[...] accesses inside setInfluent(), plus the 'time' array.
    influent_required = [
        "time",
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2",
        "S_ch4", "S_IC", "S_IN", "S_I",
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4",
        "X_pro", "X_ac", "X_h2", "X_I",
        "S_cation", "S_anion",
    ]
    # initial_state[...][0] accesses for the reactor state at t0.
    initial_required = [
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2",
        "S_ch4", "S_IC", "S_IN", "S_I",
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4",
        "X_pro", "X_ac", "X_h2", "X_I",
        "S_cation", "S_anion",
        "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion",
        "S_hco3_ion", "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
    ]

    # --- download both inputs from S3 -----------------------------------
    faasr_get_file(remote_folder=input_folder, remote_file=influent_file,
                   local_folder=".", local_file=influent_file)
    faasr_get_file(remote_folder=input_folder, remote_file=initial_file,
                   local_folder=".", local_file=initial_file)
    faasr_log(f"validate_inputs: downloaded {influent_file} and {initial_file} "
              f"from prefix '{input_folder}'.")

    def _check(df, name, required, min_rows):
        problems = []

        # 1. required columns present
        missing = [c for c in required if c not in df.columns]
        if missing:
            problems.append(f"missing required columns: {missing}")

        # 2. enough rows
        if len(df) < min_rows:
            problems.append(f"expected at least {min_rows} row(s), found {len(df)}")

        # Only inspect the columns that are actually present.
        present = [c for c in required if c in df.columns]

        # 3. numeric dtype
        non_numeric = [c for c in present
                       if not pd.api.types.is_numeric_dtype(df[c])]
        if non_numeric:
            problems.append(f"non-numeric columns: {non_numeric}")

        numeric = [c for c in present if c not in non_numeric]

        # 4. no missing / non-finite values
        if numeric:
            sub = df[numeric]
            nan_cols = [c for c in numeric if sub[c].isna().any()]
            if nan_cols:
                problems.append(f"columns with missing values: {nan_cols}")
            inf_cols = [c for c in numeric
                        if np.isinf(sub[c].to_numpy(dtype=float,
                                                    na_value=0.0)).any()]
            if inf_cols:
                problems.append(f"columns with non-finite values: {inf_cols}")

            # 5. concentrations must be non-negative
            conc = [c for c in numeric if c != "time"]
            neg_cols = [c for c in conc if (df[c] < 0).any()]
            if neg_cols:
                problems.append(f"columns with negative values: {neg_cols}")

        # 6. time must be strictly increasing (if present)
        if "time" in numeric and not df["time"].is_monotonic_increasing:
            problems.append("'time' column is not monotonically increasing")

        if problems:
            msg = f"Validation FAILED for {name}: " + "; ".join(problems)
            faasr_log(msg)
            raise ValueError(msg)

        faasr_log(f"validate_inputs: {name} OK "
                  f"({len(df)} rows, {len(df.columns)} columns).")

    influent = pd.read_csv(influent_file)
    initial = pd.read_csv(initial_file)

    _check(influent, influent_file, influent_required, min_rows=2)
    _check(initial, initial_file, initial_required, min_rows=1)

    # --- re-publish the validated inputs for the downstream simulation ---
    faasr_put_file(local_folder=".", local_file=influent_file,
                   remote_folder="pyadm1-validated", remote_file=influent_file)
    faasr_put_file(local_folder=".", local_file=initial_file,
                   remote_folder="pyadm1-validated", remote_file=initial_file)

    faasr_log("validate_inputs: both inputs validated and published to "
              "prefix 'pyadm1-validated'. Proceeding to simulation.")
