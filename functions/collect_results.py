import csv
import json


def collect_results(n_samples: int = 4):
    invocation_id = faasr_invocation_id()
    rows = []

    for rank in range(1, n_samples + 1):
        faasr_get_file(
            local_file=f"sample_{rank}.json",
            remote_file=f"sample_{rank}.json",
            local_folder="/tmp",
            remote_folder=f"generator-demo/{invocation_id}/samples",
        )
        with open(f"/tmp/sample_{rank}.json") as f:
            rows.append(json.load(f))

    rows.sort(key=lambda r: r["rank"])
    faasr_log(f"Collected {len(rows)} samples: " + ", ".join(f"{r['label']}=({r['x']:.2f},{r['y']:.4f})" for r in rows))

    with open("/tmp/samples.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "label", "x", "y"])
        writer.writeheader()
        writer.writerows(rows)

    faasr_put_file(
        local_file="samples.csv",
        remote_file="samples.csv",
        local_folder="/tmp",
        remote_folder=f"generator-demo/{invocation_id}",
    )
