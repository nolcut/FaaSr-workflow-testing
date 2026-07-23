"""FaaSr step 3: remove-spikes.

Detect and replace isolated sensor spikes in BOTH the online sensor channels
Q (flow) and T (temperature). A Hampel filter is used: a point is flagged as a
spike when it deviates from the local (rolling) median by more than
`n_sigmas` scaled median-absolute-deviations. Flagged points are replaced with
the local median, which is exactly the "local median" replacement requested.
"""

try:
    from FaaSr_py.client.py_client_stubs import faasr_get_file, faasr_put_file, faasr_log
except Exception:  # pragma: no cover
    pass

import numpy as np
import pandas as pd

SPIKE_COLUMNS = ["Q", "T"]
# 1.4826 scales MAD to be a consistent estimator of the std-dev for normal data.
_MAD_SCALE = 1.4826


def _hampel(series, window=7, n_sigmas=3.0):
    """Return (cleaned_series, n_spikes) using a centered Hampel filter."""
    s = series.astype(float).copy()
    med = s.rolling(window=window, center=True, min_periods=1).median()
    abs_dev = (s - med).abs()
    mad = abs_dev.rolling(window=window, center=True, min_periods=1).median()
    threshold = n_sigmas * _MAD_SCALE * mad
    # Guard against a zero-MAD window (perfectly flat region) producing false spikes.
    is_spike = (abs_dev > threshold) & (threshold > 0)
    cleaned = s.mask(is_spike, med)
    return cleaned, int(is_spike.sum())


def remove_spikes(folder, input_file="influent_filled.csv",
                  output_file="influent_despiked.csv",
                  window=7, n_sigmas=3.0):
    faasr_log(f"remove_spikes: downloading {folder}/{input_file}")
    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file="in.csv")

    df = pd.read_csv("in.csv")

    for col in SPIKE_COLUMNS:
        if col not in df.columns:
            faasr_log(f"remove_spikes: WARNING - column '{col}' not found; skipping")
            continue
        cleaned, n_spikes = _hampel(df[col], window=window, n_sigmas=n_sigmas)
        df[col] = cleaned
        faasr_log(f"remove_spikes: replaced {n_spikes} spike(s) in '{col}' "
                  f"with the local median")

    df.to_csv(output_file, index=False)
    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"remove_spikes: wrote {folder}/{output_file}")
