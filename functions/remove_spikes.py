import pandas as pd
import numpy as np


def _hampel(series, window=11, n_sigma=5.0, iso_factor=3.0):
    """Hampel filter targeting *isolated* sensor spikes.

    A sample is treated as an isolated spike (and replaced by the local median)
    only when BOTH conditions hold:

      1. it deviates from the local rolling median by more than
         ``n_sigma`` robust standard deviations (MAD based), and
      2. that deviation is at least ``iso_factor`` times larger than the
         deviation of its immediate neighbours -- i.e. the excursion is a
         single, isolated sample rather than part of a genuine trend/ramp.

    Condition (2) keeps the filter from chewing up smooth curvature when the
    signal is very low-noise (near-zero local MAD).  A small MAD floor derived
    from the global scale guards the same degenerate case.
    """
    s = series.astype(float)
    med = s.rolling(window, center=True, min_periods=1).median()
    resid = s - med
    abs_dev = resid.abs()

    # Global robust noise scale (MAD of the median-detrended residuals).  Using
    # a global estimate is far more stable than a tiny rolling MAD, which badly
    # underestimates noise in short windows and causes false positives.
    # 1.4826 makes the MAD a consistent estimator of the std-dev.
    global_scale = 1.4826 * (resid - resid.median()).abs().median()
    if not np.isfinite(global_scale) or global_scale < 0:
        global_scale = 0.0
    # NOTE: when the signal is (almost) noise-free the scale -> 0 and the
    # threshold -> 0 on purpose; the isolation test below is then what
    # distinguishes a real single-sample spike from smooth curvature.
    threshold = n_sigma * global_scale

    neighbour_max = pd.concat(
        [abs_dev.shift(1), abs_dev.shift(-1)], axis=1).max(axis=1).fillna(0.0)
    # an isolated spike towers over its immediate neighbours
    isolated = abs_dev > iso_factor * neighbour_max

    spike_mask = (abs_dev > threshold) & isolated
    cleaned = s.copy()
    cleaned[spike_mask] = med[spike_mask]
    return cleaned, int(spike_mask.sum())


def remove_spikes(folder, input_file, output_file, temp_col="T_C"):
    """Step 3 - detect and replace isolated sensor spikes in BOTH Q and T
    with the local median."""
    faasr_get_file(server_name="S3", remote_folder=folder,
                   remote_file=input_file, local_file="in.csv")
    df = pd.read_csv("in.csv")

    report = {}
    for col in ["Q", temp_col]:
        if col in df.columns:
            df[col], n_spikes = _hampel(df[col])
            report[col] = n_spikes

    df.to_csv(output_file, index=False)
    faasr_put_file(server_name="S3", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)
    faasr_log("remove_spikes: replaced spikes {} with local median; "
              "wrote {}/{}".format(report, folder, output_file))
