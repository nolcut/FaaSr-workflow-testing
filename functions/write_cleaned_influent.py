def write_cleaned_influent(folder: str, input1: str, output1: str) -> None:
    import pandas as pd

    local_in = "influent_outliers_removed.csv"

    faasr_log(f"write_cleaned_influent: fetching {input1} from folder {folder}")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    # Validate the fully cleaned dataset can be read, but pass it through exactly
    # as received (no further transformation) by re-uploading the same local file.
    df = pd.read_csv(local_in)
    faasr_log(
        f"write_cleaned_influent: verified {len(df)} rows x {len(df.columns)} columns "
        f"(columns: {list(df.columns)})"
    )

    faasr_put_file(local_file=local_in, remote_folder=folder, remote_file=output1)
    faasr_log(f"write_cleaned_influent: wrote final cleaned influent {output1} to folder {folder}")
