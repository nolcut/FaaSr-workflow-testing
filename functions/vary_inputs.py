import pandas as pd
import numpy as np


def vary_inputs(folder, input_file, output_prefix, count=20,
                srt_min=10.0, srt_max=30.0, v_liq=3400.0):
    """Step 5 - create `count` derived initial-condition files that vary the
    solids retention time (SRT).

    SRT controls the digester feed/dilution rate.  In ADM1 the influent flow is
    q_ad = V_liq / SRT (V_liq = 3400 m^3 for the BSM2 reactor).  We sweep SRT
    linearly from `srt_min` to `srt_max` days and write one initial-state file
    per scenario, each an exact copy of the base initial state plus the SRT and
    the corresponding q_ad it implies.  Files are named
    <output_prefix>_<rank>.csv for rank = 1 .. count so the ranked pyadm1
    action can pick its own scenario.
    """
    faasr_get_file(server_name="S3", remote_folder=folder,
                   remote_file=input_file, local_file="init.csv")
    base = pd.read_csv("init.csv")

    srts = np.linspace(float(srt_min), float(srt_max), int(count))
    for i, srt in enumerate(srts, start=1):
        variant = base.copy()
        variant["SRT"] = float(srt)
        variant["q_ad"] = float(v_liq) / float(srt)
        fname = "{}_{}.csv".format(output_prefix, i)
        variant.to_csv(fname, index=False)
        faasr_put_file(server_name="S3", local_file=fname,
                       remote_folder=folder, remote_file=fname)

    faasr_log("vary_inputs: wrote {} SRT-varied initial files ({}..{} d) as "
              "{}/{}_1..{}.csv".format(int(count), srt_min, srt_max,
                                       folder, output_prefix, int(count)))
