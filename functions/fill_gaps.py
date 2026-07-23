import pandas as pd


def fill_gaps(folder, input_file, output_file):
    """Step 2 - forward-fill missing S_cation and S_anion values.

    These two ionic columns are occasionally missing; carry the last valid
    reading forward.  A trailing back-fill handles any leading gap at the very
    start of the record so no NaN is left behind.
    """
    faasr_get_file(server_name="S3", remote_folder=folder,
                   remote_file=input_file, local_file="in.csv")
    df = pd.read_csv("in.csv")

    filled = {}
    for col in ["S_cation", "S_anion"]:
        if col in df.columns:
            n_missing = int(df[col].isna().sum())
            df[col] = df[col].ffill().bfill()
            filled[col] = n_missing

    df.to_csv(output_file, index=False)
    faasr_put_file(server_name="S3", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log("fill_gaps: forward-filled missing values {}; wrote {}/{}".format(
        filled, folder, output_file))
