import numpy as np
import pandas as pd

# Step 5: vary-inputs
# Produce 20 initial-state files derived from digester_initial.csv, each one
# tagged with a different Solids/Hydraulic Retention Time (SRT). In this
# single-tank BSM2 configuration SRT = V_liq / Q_feed, so a chosen SRT maps
# directly to the digester feed flow rate q_ad used by the simulation:
#       q_ad = V_liq / SRT           [m3/d]
# The reactor initial concentrations are copied unchanged; only the SRT (and
# the derived q_ad) differ between the 20 variants. Rank r of the downstream
# pyadm1 action reads digester_initial_<r>.csv.

FOLDER = "PyADM1-orig"

N_VARIANTS = 20
V_LIQ = 3400.0          # m3, liquid volume (BSM2)
SRT_MIN_DAYS = 15.0     # sweep range for retention time
SRT_MAX_DAYS = 40.0


def vary_inputs():
    faasr_log("vary-inputs: downloading base digester_initial.csv")
    faasr_get_file(
        server_name="S3",
        remote_folder=FOLDER,
        remote_file="digester_initial.csv",
        local_folder=".",
        local_file="digester_initial.csv",
    )

    base = pd.read_csv("digester_initial.csv")

    srt_values = np.linspace(SRT_MIN_DAYS, SRT_MAX_DAYS, N_VARIANTS)

    for i, srt in enumerate(srt_values):
        rank = i + 1  # FaaSr ranks are 1-based
        variant = base.copy()
        q_ad = V_LIQ / float(srt)
        variant["SRT"] = float(srt)
        variant["q_ad"] = q_ad

        local_name = f"digester_initial_{rank}.csv"
        variant.to_csv(local_name, index=False)
        faasr_put_file(
            server_name="S3",
            local_folder=".",
            local_file=local_name,
            remote_folder=FOLDER,
            remote_file=local_name,
        )
        faasr_log(
            f"vary-inputs: wrote {local_name} (SRT={srt:.2f} d, q_ad={q_ad:.3f} m3/d)"
        )

    faasr_log(f"vary-inputs: produced {N_VARIANTS} SRT-varied initial-state files")
