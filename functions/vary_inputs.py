import numpy as np
import pandas as pd


def vary_inputs(folder: str, input1: str, output1: str) -> None:
    """Create 20 derived digester initial-state files that vary the SRT.

    Reads the source initial-state CSV (input1) from the S3 folder, generates a
    deterministic linearly-spaced sweep of 20 solids-retention-time (SRT) values
    over a plausible mesophilic-digester range, and for each rank 1..20 writes one
    derived initial-state file (output1 with {rank} substituted). Every field of
    the source file is carried over unchanged; only the SRT parameter is set to the
    rank-mapped value. The 20 shards feed the 20 ranked pyadm1 simulation instances.
    """
    # This function is NOT ranked: the fan-out count is fixed by the workflow spec.
    n_cases = 20

    faasr_log(f"vary_inputs: downloading source initial-state '{input1}' from folder '{folder}'")
    local_source = "digester_initial_source.csv"
    faasr_get_file(local_file=local_source, remote_folder=folder, remote_file=input1)

    source = pd.read_csv(local_source)
    if source.empty:
        msg = f"vary_inputs: source initial-state file '{input1}' has no rows"
        faasr_log(msg)
        raise ValueError(msg)

    # Deterministic SRT sweep: linearly spaced over a plausible mesophilic
    # anaerobic-digester solids-retention-time range (days). rank i -> srt_values[i-1].
    srt_min_days = 10.0
    srt_max_days = 60.0
    srt_values = np.linspace(srt_min_days, srt_max_days, n_cases)
    faasr_log(
        f"vary_inputs: SRT sweep over [{srt_min_days}, {srt_max_days}] days, "
        f"{n_cases} cases: {', '.join(f'{v:.4f}' for v in srt_values)}"
    )

    for rank in range(1, n_cases + 1):
        srt = float(srt_values[rank - 1])
        derived = source.copy()
        # Carry over all source fields unchanged; set only the SRT parameter.
        derived["SRT"] = srt

        local_out = f"digester_initial_{rank}.csv"
        derived.to_csv(local_out, index=False)

        remote_out = output1.replace("{rank}", str(rank))
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(
            f"vary_inputs: wrote case rank={rank} SRT={srt:.4f} d -> '{remote_out}' in folder '{folder}'"
        )

    faasr_log(f"vary_inputs: completed {n_cases} derived initial-state files")
