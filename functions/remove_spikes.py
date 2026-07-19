import pandas as pd
import numpy as np
import tempfile
import os

# Rolling-window MAD spike detection parameters
_WINDOW = 49        # ~12 hours at 15-min resolution (must be odd for centered median)
_MAD_THRESH = 5.0   # flag if |x - rolling_median| > threshold * rolling_MAD
_MAX_RUN = 3        # runs longer than this are NOT replaced (true step change)

def _remove_spikes_column(series: pd.Series, window: int, mad_thresh: float, max_run: int) -> pd.Series:
    s = series.copy()
    roll = s.rolling(window, center=True, min_periods=window // 2)
    med = roll.median()
    mad = roll.apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True)
    # avoid division by zero: if MAD==0, no spike can be detected
    mad_safe = mad.replace(0, np.nan)
    flagged = (s - med).abs() > mad_thresh * mad_safe

    # Only replace *isolated* spikes: runs of flagged points <= max_run
    result = s.copy()
    i = 0
    arr = flagged.to_numpy()
    med_arr = med.to_numpy()
    n = len(arr)
    while i < n:
        if arr[i]:
            run_start = i
            while i < n and arr[i]:
                i += 1
            run_len = i - run_start
            if run_len <= max_run:
                for j in range(run_start, run_start + run_len):
                    if not np.isnan(med_arr[j]):
                        result.iloc[j] = med_arr[j]
        else:
            i += 1
    return result


def remove_spikes(folder: str, input1: str, output1: str) -> None:
    faasr_log("remove_spikes: starting spike removal")

    with tempfile.TemporaryDirectory() as tmp:
        local_in = os.path.join(tmp, "in.csv")
        local_out = os.path.join(tmp, "out.csv")

        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
        df = pd.read_csv(local_in)
        faasr_log(f"remove_spikes: loaded {len(df)} rows")

        for col in ("Q", "T_ad"):
            if col not in df.columns:
                raise ValueError(f"Expected column '{col}' not found in input")
            original = df[col].copy()
            df[col] = _remove_spikes_column(df[col], _WINDOW, _MAD_THRESH, _MAX_RUN)
            replaced = (df[col] != original).sum()
            faasr_log(f"remove_spikes: {col} — {replaced} spike values replaced")

        df.to_csv(local_out, index=False)
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
        faasr_log("remove_spikes: done")
