import json


def generate_samples(x_val: float, label: str):
    rank = faasr_rank()["rank"]
    y_val = x_val ** 2
    faasr_log(f"Rank {rank}: label={label}, x={x_val:.2f}, y={y_val:.4f}")

    data = {"rank": rank, "label": label, "x": x_val, "y": y_val}
    local_path = f"/tmp/sample_{rank}.json"
    with open(local_path, "w") as f:
        json.dump(data, f)

    faasr_put_file(
        local_file=f"sample_{rank}.json",
        remote_file=f"sample_{rank}.json",
        local_folder="/tmp",
        remote_folder=f"generator-demo/{faasr_invocation_id()}/samples",
    )
