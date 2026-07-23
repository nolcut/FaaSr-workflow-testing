import pandas as pd

# Step 3: remove-spikes
# The high-rate sensor channels Q (flow) and T_C (temperature) occasionally
# report isolated single-sample spikes (bad reads / telemetry glitches).
# Detect them with a Hampel filter (rolling-median + scaled MAD) and replace
# each flagged sample with the local rolling median.

FOLDER = "PyADM1-orig"

WINDOW = 7        # rolling window (samples), centered
N_SIGMA = 3.0     # robust z-score threshold
K_MAD = 1.4826    # scale factor: MAD -> std for a normal distribution


def _hampel(series):
    med = series.rolling(WINDOW, center=True, min_periods=1).median()
    abs_dev = (series - med).abs()
    mad = abs_dev.rolling(WINDOW, center=True, min_periods=1).median()
    threshold = N_SIGMA * K_MAD * mad
    spikes = abs_dev > threshold
    cleaned = series.copy()
    cleaned[spikes] = med[spikes]
    return cleaned, int(spikes.sum())


def remove_spikes():
    faasr_log("remove-spikes: downloading gap-filled influent")
    faasr_get_file(
        server_name="S3",
        remote_folder=FOLDER,
        remote_file="influent_filled.csv",
        local_folder=".",
        local_file="influent_filled.csv",
    )

    df = pd.read_csv("influent_filled.csv")

    for col in ("Q", "T_C"):
        if col in df.columns:
            df[col], n = _hampel(df[col].astype(float))
            faasr_log(f"remove-spikes: replaced {n} isolated spikes in {col} with local median")

    df.to_csv("influent_despiked.csv", index=False)
    faasr_put_file(
        server_name="S3",
        local_folder=".",
        local_file="influent_despiked.csv",
        remote_folder=FOLDER,
        remote_file="influent_despiked.csv",
    )
    faasr_log("remove-spikes: wrote influent_despiked.csv")
