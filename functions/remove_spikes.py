import pandas as pd
import numpy as np

SPIKE_COLUMNS = ["Q", "T"]
WINDOW = 5
MAD_THRESHOLD = 3.0


def _despike(series: pd.Series, window: int, threshold: float) -> pd.Series:
    """Replace isolated spikes (single outlier not part of a consecutive run) with local rolling median."""
    s = series.copy()
    roll = s.rolling(window=window, center=True, min_periods=1)
    rolling_median = roll.median()
    rolling_mad = roll.apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True)

    # Avoid division by zero: where MAD == 0 no spike can be detected
    with np.errstate(invalid="ignore", divide="ignore"):
        deviation = np.abs(s - rolling_median) / rolling_mad.replace(0, np.nan)

    is_outlier = deviation > threshold

    # Only replace ISOLATED outliers (runs of length 1)
    # A point is isolated if neither its predecessor nor its successor is also an outlier
    outlier_arr = is_outlier.to_numpy(dtype=bool, na_value=False)
    prev_out = np.concatenate([[False], outlier_arr[:-1]])
    next_out = np.concatenate([outlier_arr[1:], [False]])
    isolated = outlier_arr & ~prev_out & ~next_out

    s[isolated] = rolling_median[isolated]
    return s


def remove_spikes(folder: str, input1: str, output1: str) -> None:
    local_in = "influent_filled.csv"
    local_out = "influent_despiked.csv"

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    faasr_log(f"remove_spikes: read {input1}")

    df = pd.read_csv(local_in)

    for col in SPIKE_COLUMNS:
        if col not in df.columns:
            faasr_log(f"remove_spikes: ERROR — column {col} not found")
            raise ValueError(f"Column {col} not found in input")
        original = df[col].copy()
        df[col] = _despike(df[col], window=WINDOW, threshold=MAD_THRESHOLD)
        n_replaced = (df[col] != original).sum()
        faasr_log(f"remove_spikes: {col} — replaced {n_replaced} isolated spikes")

    df.to_csv(local_out, index=False)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"remove_spikes: wrote {output1}")
