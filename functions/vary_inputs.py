# Step 5: vary-inputs
# Create N (=20) initial-condition files derived from digester_initial.csv, each
# corresponding to a different Solids Retention Time (SRT, days). SRT is realised
# in the simulation as a digester feed flow q_ad = V_liq / SRT (V_liq = 3400 m^3,
# see PyADM1). Each variant is a copy of the base initial state with an added
# "SRT" column that the PyADM1 step reads to set the flow rate.

def vary_inputs(folder, input_file="digester_initial.csv",
                output_prefix="digester_initial", n=20,
                srt_min=15.0, srt_max=50.0):
    import pandas as pd
    import numpy as np

    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file=input_file)
    base = pd.read_csv(input_file)

    srt_values = np.linspace(float(srt_min), float(srt_max), int(n))
    for i, srt in enumerate(srt_values, start=1):   # ranks are 1..N
        variant = base.copy()
        variant["SRT"] = float(srt)
        out = f"{output_prefix}_{i}.csv"
        variant.to_csv(out, index=False)
        faasr_put_file(local_folder=".", local_file=out,
                       remote_folder=folder, remote_file=out)
        faasr_log(f"vary_inputs: wrote {folder}/{out} (SRT={srt:.3f} d)")

    faasr_log(f"vary_inputs: created {int(n)} SRT-varied initial-state files "
              f"(SRT {srt_min}-{srt_max} d)")
