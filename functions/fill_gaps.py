def fill_gaps(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    local_in = "influent_solubles_converted.csv"
    local_out = "influent_gaps_filled.csv"

    faasr_log(f"fill_gaps: fetching {input1} from folder {folder}")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    df = pd.read_csv(local_in)

    target_cols = ["S_cation", "S_anion"]
    missing = [c for c in target_cols if c not in df.columns]
    if missing:
        msg = (
            f"fill_gaps: required column(s) {missing} not found in {input1}; "
            f"columns present: {list(df.columns)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Forward-fill missing values in S_cation and S_anion, leaving all other
    # columns unchanged. Column order/headers are preserved by in-place assignment.
    n_before = int(df[target_cols].isna().sum().sum())
    df[target_cols] = df[target_cols].ffill()
    n_after = int(df[target_cols].isna().sum().sum())
    faasr_log(
        f"fill_gaps: forward-filled S_cation/S_anion — {n_before} missing before, "
        f"{n_after} remaining (leading NaNs with no prior value cannot be filled)"
    )

    df.to_csv(local_out, index=False)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"fill_gaps: wrote {output1} to folder {folder}")
