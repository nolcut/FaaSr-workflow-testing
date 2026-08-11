def validate(folder: str, input1: str, input2: str, output1: str) -> None:
    """Sanity-check the cleaned influent and the initial-state file before PyADM1.

    Runs a battery of consistency checks and writes one report row per check
    (check name, target file, PASS/FAIL status, descriptive message) to a CSV.
    The report is always written; individual check failures are recorded as FAIL
    rows rather than raising, so downstream tooling can inspect every result.
    """
    import pandas as pd
    import numpy as np

    # --- Expected column definitions (kept explicit per the workflow spec) ---
    # The 22 COD columns (divided by 1000 upstream): 10 soluble + 12 particulate.
    soluble_cod = ["S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro",
                   "S_ac", "S_h2", "S_ch4", "S_I"]
    particulate_cod = ["X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa",
                       "X_fa", "X_c4", "X_pro", "X_ac", "X_h2", "X_I"]
    cod_columns = soluble_cod + particulate_cod                      # 22 COD columns
    untouched = ["S_IC", "S_IN", "S_cation", "S_anion"]              # left as-is upstream
    flow_col = "Q"
    temp_celsius_candidates = ("T (C)", "T(C)", "T_C")
    temp_fahrenheit_candidates = ("T (F)", "T(F)", "T_F")

    # Expected influent columns: 22 COD + 4 untouched + Q + T = 28 (plus a temp column).
    expected_influent = cod_columns + untouched + [flow_col]

    # The 36 state variables PyADM1 reads from the initial-state file.
    required_initial = [
        "S_su", "S_aa", "S_fa", "S_va", "S_bu", "S_pro", "S_ac", "S_h2", "S_ch4",
        "S_IC", "S_IN", "S_I",
        "X_xc", "X_ch", "X_pr", "X_li", "X_su", "X_aa", "X_fa", "X_c4", "X_pro",
        "X_ac", "X_h2", "X_I",
        "S_cation", "S_anion",
        "S_H_ion", "S_va_ion", "S_bu_ion", "S_pro_ion", "S_ac_ion", "S_hco3_ion",
        "S_nh3", "S_gas_h2", "S_gas_ch4", "S_gas_co2",
    ]

    CADENCE_DAYS = 1.0 / 96.0   # 15 minutes expressed in days
    results = []

    def record(check, target, ok, message):
        status = "PASS" if ok else "FAIL"
        results.append({"check": check, "target_file": target,
                        "status": status, "message": message})
        faasr_log(f"validate: [{status}] {check} ({target}) - {message}")

    # ---------------------------------------------------------------- load files
    faasr_log(f"validate: downloading cleaned influent '{input1}' and initial state '{input2}'")
    faasr_get_file(local_file="digester_influent.csv", remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file="digester_initial.csv", remote_folder=folder, remote_file=input2)
    inf = pd.read_csv("digester_influent.csv")
    ini = pd.read_csv("digester_initial.csv")
    faasr_log(f"validate: influent {inf.shape}, initial {ini.shape}")

    # Resolve the temperature column name in the influent.
    temp_col = next((c for c in temp_celsius_candidates if c in inf.columns), None)

    # ------------------------------------------ influent: expected columns present
    missing_cols = [c for c in expected_influent if c not in inf.columns]
    has_temp = temp_col is not None
    ok = (not missing_cols) and has_temp
    msg = ("all 28 expected ADM1 columns present (22 COD + S_IC/S_IN/S_cation/S_anion "
           f"+ Q + T)" if ok else
           f"missing: {missing_cols}" + ("" if has_temp else " + temperature column"))
    record("influent_expected_columns_present", input1, ok, msg)

    # ------------------------------------------------ influent: 22 COD column count
    present_cod = [c for c in cod_columns if c in inf.columns]
    ok = len(present_cod) == 22
    record("influent_cod_column_count", input1, ok,
           f"found {len(present_cod)}/22 COD columns" +
           ("" if ok else f"; missing {[c for c in cod_columns if c not in inf.columns]}"))

    # ------------------------------------- influent: temperature converted to Celsius
    stray_f = [c for c in temp_fahrenheit_candidates if c in inf.columns]
    if temp_col is None:
        record("influent_temperature_celsius", input1, False,
               "no Celsius temperature column found (expected 'T (C)')")
    elif stray_f:
        record("influent_temperature_celsius", input1, False,
               f"Fahrenheit column {stray_f} still present alongside '{temp_col}'")
    else:
        tvals = inf[temp_col].astype(float)
        plausible = bool(tvals.between(-5, 80).all())
        record("influent_temperature_celsius", input1, plausible,
               f"'{temp_col}' present, no Fahrenheit column; range "
               f"[{tvals.min():.3f}, {tvals.max():.3f}] °C"
               + ("" if plausible else " outside plausible digester range"))

    # -------------------------------------------- influent: flow present, m3/d units
    if flow_col not in inf.columns:
        record("influent_flow_units_m3d", input1, False, "flow column 'Q' not found")
    else:
        q = inf[flow_col].astype(float)
        ok = bool((q >= 0).all())
        record("influent_flow_units_m3d", input1, ok,
               f"Q present (expected m3/d); range [{q.min():.3f}, {q.max():.3f}]"
               + ("" if ok else "; contains negative flow"))

    # ------------------------------------------------- influent: no missing/NaN values
    n_nan = int(inf.isna().sum().sum())
    if n_nan == 0:
        record("influent_no_missing_values", input1, True, "no missing/NaN values")
    else:
        nan_cols = inf.columns[inf.isna().any()].tolist()
        record("influent_no_missing_values", input1, False,
               f"{n_nan} NaN value(s) in columns {nan_cols}")

    # ---------------------------------- influent: non-negativity of concentrations/flow
    # Concentrations and flow must be >= 0; exclude 'time' and the temperature column.
    conc_cols = [c for c in inf.columns
                 if c not in ("time", temp_col) and
                 pd.api.types.is_numeric_dtype(inf[c])]
    neg = {c: float(inf[c].min()) for c in conc_cols if (inf[c] < 0).any()}
    if not neg:
        record("influent_non_negativity", input1, True,
               f"all {len(conc_cols)} concentration/flow columns >= 0")
    else:
        record("influent_non_negativity", input1, False,
               f"negative values in {list(neg.keys())} (mins {neg})")

    # -------------------------------------------------- influent: time monotonic index
    if "time" not in inf.columns:
        record("influent_time_monotonic", input1, False, "'time' column not found")
        record("influent_time_cadence_15min", input1, False, "'time' column not found")
    else:
        t = inf["time"].astype(float)
        diffs = t.diff().dropna()
        mono = bool((diffs > 0).all())
        record("influent_time_monotonic", input1, mono,
               "time strictly increasing" if mono
               else f"non-monotonic time (min step {diffs.min():.6g} days)")

        # --------------------------------- influent: 15-minute sampling cadence
        max_dev = float((diffs - CADENCE_DAYS).abs().max()) if len(diffs) else 0.0
        cadence_ok = max_dev <= 1e-6
        record("influent_time_cadence_15min", input1, cadence_ok,
               f"expected 15-min ({CADENCE_DAYS:.6f} d) cadence; max deviation "
               f"{max_dev:.3g} d" + ("" if cadence_ok else " exceeds tolerance"))

    # -------------------------------- influent: S_cation/S_anion forward-filled (no gaps)
    gap_cols = [c for c in ("S_cation", "S_anion")
                if c in inf.columns and inf[c].isna().any()]
    absent = [c for c in ("S_cation", "S_anion") if c not in inf.columns]
    if absent:
        record("influent_cation_anion_gapfilled", input1, False,
               f"columns absent: {absent}")
    elif gap_cols:
        record("influent_cation_anion_gapfilled", input1, False,
               f"remaining gaps in {gap_cols}")
    else:
        record("influent_cation_anion_gapfilled", input1, True,
               "S_cation and S_anion fully populated (forward-filled, no gaps)")

    # ---------------------------- initial state: all required PyADM1 variables present
    missing_ini = [c for c in required_initial if c not in ini.columns]
    if not missing_ini:
        record("initial_required_state_present", input2, True,
               f"all {len(required_initial)} PyADM1 initial-state variables present")
    else:
        record("initial_required_state_present", input2, False,
               f"missing required state variables: {missing_ini}")

    # ------------------------ initial state: non-negativity + no NaN (sanity/consistency)
    present_ini = [c for c in required_initial if c in ini.columns]
    ini_nan = [c for c in present_ini if ini[c].isna().any()]
    ini_neg = {c: float(ini[c].min()) for c in present_ini if (ini[c] < 0).any()}
    if not ini_nan and not ini_neg:
        record("initial_values_valid", input2, True,
               "initial-state values present and non-negative")
    else:
        record("initial_values_valid", input2, False,
               f"NaN in {ini_nan}; negative in {list(ini_neg.keys())}")

    # --------------------------------------------------------------- write report
    report = pd.DataFrame(results, columns=["check", "target_file", "status", "message"])
    n_fail = int((report["status"] == "FAIL").sum())
    report.to_csv("validation_report.csv", index=False)
    faasr_put_file(local_file="validation_report.csv", remote_folder=folder, remote_file=output1)
    faasr_log(f"validate: wrote '{output1}' - {len(report)} checks, {n_fail} FAIL")
