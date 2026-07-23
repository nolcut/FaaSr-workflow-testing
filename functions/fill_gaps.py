# Step 2: fill-gaps
# Forward-fill missing S_cation and S_anion values (titration/ion columns that
# are only occasionally reported). A trailing back-fill covers any leading NaNs.

def fill_gaps(folder, input_file="influent_converted.csv",
              output_file="influent_filled.csv"):
    import pandas as pd

    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file=input_file)
    df = pd.read_csv(input_file)

    for c in ["S_cation", "S_anion"]:
        if c in df.columns:
            n_missing = int(df[c].isna().sum())
            df[c] = df[c].ffill().bfill()
            faasr_log(f"fill_gaps: forward-filled {n_missing} missing values in '{c}'")

    df.to_csv(output_file, index=False)
    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"fill_gaps: wrote {folder}/{output_file}")
