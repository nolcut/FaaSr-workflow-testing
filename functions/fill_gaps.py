import pandas as pd

# Step 2: fill-gaps
# The ionic strength surrogates S_cation and S_anion come from an
# intermittent lab assay and frequently have missing entries. Forward-fill
# them so every 15-min row carries the most recent measured value (a leading
# gap is back-filled so the very first rows are also valid).

FOLDER = "PyADM1-orig"


def fill_gaps():
    faasr_log("fill-gaps: downloading converted influent")
    faasr_get_file(
        server_name="S3",
        remote_folder=FOLDER,
        remote_file="influent_converted.csv",
        local_folder=".",
        local_file="influent_converted.csv",
    )

    df = pd.read_csv("influent_converted.csv")

    for col in ("S_cation", "S_anion"):
        if col in df.columns:
            n_missing = int(df[col].isna().sum())
            df[col] = df[col].ffill().bfill()
            faasr_log(f"fill-gaps: forward-filled {n_missing} missing values in {col}")

    df.to_csv("influent_filled.csv", index=False)
    faasr_put_file(
        server_name="S3",
        local_folder=".",
        local_file="influent_filled.csv",
        remote_folder=FOLDER,
        remote_file="influent_filled.csv",
    )
    faasr_log("fill-gaps: wrote influent_filled.csv")
