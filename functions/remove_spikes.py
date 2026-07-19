def remove_spikes(folder: str, input1: str, output1: str) -> None:
    import pandas as pd
    import numpy as np
    import tempfile, os

    WINDOW = 11       # rolling window size (must be odd for symmetric centering)
    MAD_THRESH = 3.0  # spike if |value - median| > MAD_THRESH * MAD

    local_in = tempfile.mktemp(suffix=".csv")
    local_out = tempfile.mktemp(suffix=".csv")

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"remove_spikes: read {input1} from {folder}")

    df = pd.read_csv(local_in)

    def despike(series):
        s = series.copy()
        half = WINDOW // 2
        vals = s.values.astype(float)
        n = len(vals)
        for i in range(n):
            lo = max(0, i - half)
            hi = min(n, i + half + 1)
            window_vals = vals[lo:hi]
            med = np.median(window_vals)
            mad = np.median(np.abs(window_vals - med))
            # avoid replacing genuine step changes: only replace isolated single-point spikes
            # (neighbours must NOT also be spikes — check them at a looser threshold)
            if mad == 0:
                continue
            if abs(vals[i] - med) > MAD_THRESH * mad:
                # verify it is isolated: at least one immediate neighbour is not a spike
                prev_ok = (i == 0) or (abs(vals[i - 1] - med) <= MAD_THRESH * mad)
                next_ok = (i == n - 1) or (abs(vals[i + 1] - med) <= MAD_THRESH * mad)
                if prev_ok or next_ok:
                    s.iat[i] = med
        return s

    q_orig = df["Q"].copy()
    t_orig = df["T (F)"].copy()

    df["Q"] = despike(df["Q"])
    df["T (F)"] = despike(df["T (F)"])

    n_q = int((df["Q"] != q_orig).sum())
    n_t = int((df["T (F)"] != t_orig).sum())
    faasr_log(f"remove_spikes: Q spikes replaced={n_q}, T spikes replaced={n_t}")

    df.to_csv(local_out, index=False)
    faasr_log(f"remove_spikes: writing {output1} to {folder}")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)

    os.remove(local_in)
    os.remove(local_out)
    faasr_log("remove_spikes: done")
