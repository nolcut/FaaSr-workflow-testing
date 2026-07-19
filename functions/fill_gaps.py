def fill_gaps(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import tempfile, os

    local_in = tempfile.mktemp(suffix=".csv")
    local_out = tempfile.mktemp(suffix=".csv")

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"fill_gaps: read {input1} from {folder}")

    df = pd.read_csv(local_in)

    df["S_cation"] = df["S_cation"].ffill()
    df["S_anion"] = df["S_anion"].ffill()

    df.to_csv(local_out, index=False)
    faasr_log(f"fill_gaps: writing {output1} to {folder}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    os.remove(local_in)
    os.remove(local_out)
    faasr_log("fill_gaps: done")
