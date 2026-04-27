import csv
import math
import os
import random


OBSERVABLES = ["S_ac", "S_ch4", "S_gas_ch4", "pH"]
N_MEASUREMENTS = 120
NOISE_REL = 0.05
NOISE_ABS = 1e-4
SEED = 17


def generate_synthetic_data():
    here = os.path.dirname(os.path.abspath(__file__))
    truth_path = os.path.join(here, "dynamic_out.csv")

    with open(truth_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    n_total = len(rows)
    if n_total == 0:
        raise RuntimeError(f"{truth_path} is empty")

    indices = [round(i * (n_total - 1) / (N_MEASUREMENTS - 1)) for i in range(N_MEASUREMENTS)]
    rng = random.Random(SEED)

    influent_path = os.path.join(here, "digester_influent.csv")
    times = []
    with open(influent_path) as f:
        for r in csv.DictReader(f):
            times.append(float(r["time"]))

    out_rows = []
    for idx in indices:
        rec = {"idx": idx, "time": times[idx] if idx < len(times) else float(idx)}
        for col in OBSERVABLES:
            true_val = float(rows[idx][col])
            noise = rng.gauss(0.0, 1.0) * (abs(true_val) * NOISE_REL + NOISE_ABS)
            rec[col] = true_val + noise
        out_rows.append(rec)

    local_path = "/tmp/synthetic_measurements.csv"
    with open(local_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["idx", "time"] + OBSERVABLES)
        writer.writeheader()
        writer.writerows(out_rows)

    faasr_log(
        f"Synthetic measurements: {len(out_rows)} rows, columns={OBSERVABLES}, "
        f"horizon={out_rows[0]['time']:.2f}->{out_rows[-1]['time']:.2f} d"
    )

    faasr_put_file(
        local_file="synthetic_measurements.csv",
        remote_file="synthetic_measurements.csv",
        local_folder="/tmp",
        remote_folder=f"adm1-demo/{faasr_invocation_id()}",
    )
