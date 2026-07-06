import json
import os


def reduce(folder: str, input1: str, output1: str) -> None:
    # Deterministic vocabulary / rank ordering shared across the MapReduce
    # benchmark (matches split and shuffle). Reducer rank i (1..M) handles
    # vocabulary[i-1].
    vocabulary = ["cat", "dog", "bird", "horse", "pig"]

    r = faasr_rank()
    rank = r["rank"]

    if rank < 1 or rank > len(vocabulary):
        msg = (
            f"reduce: rank {rank} is out of range for vocabulary of size "
            f"{len(vocabulary)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    assigned_word = vocabulary[rank - 1]

    # Resolve the rank-numbered input/output filenames.
    remote_in = input1.format(rank=rank).replace("{rank}", str(rank))
    remote_out = output1.format(rank=rank).replace("{rank}", str(rank))

    local_in = remote_in.rsplit("/", 1)[-1]

    faasr_log(
        f"reduce: rank={rank} assigned word='{assigned_word}', "
        f"fetching shard '{remote_in}' from folder '{folder}'"
    )

    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    with open(local_in, "r") as f:
        shard = json.load(f)

    if os.path.exists(local_in):
        os.remove(local_in)

    if not isinstance(shard, dict):
        msg = (
            f"reduce: expected a JSON object in '{remote_in}', "
            f"got {type(shard).__name__}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    shard_word = shard.get("word")
    if shard_word != assigned_word:
        msg = (
            f"reduce: rank={rank} expected shard for word '{assigned_word}' "
            f"but shard reports word '{shard_word}'"
        )
        faasr_log(msg)
        raise ValueError(msg)

    partial_counts = shard.get("partial_counts")
    if not isinstance(partial_counts, list):
        msg = (
            f"reduce: expected 'partial_counts' list in '{remote_in}', "
            f"got {type(partial_counts).__name__}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Sum the occurrence counts for this reducer's assigned word across all
    # map outputs (the flattened, shuffled partial counts).
    total = 0
    for c in partial_counts:
        if not isinstance(c, (int, float)) or isinstance(c, bool):
            msg = (
                f"reduce: non-numeric partial count {c!r} in '{remote_in}'"
            )
            faasr_log(msg)
            raise ValueError(msg)
        total += c

    total = int(total)

    result = {"word": assigned_word, "count": total}

    local_out = remote_out.rsplit("/", 1)[-1]
    with open(local_out, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(
        f"reduce: rank={rank} word='{assigned_word}' total Zi={total} "
        f"(summed {len(partial_counts)} partial counts) -> {remote_out}"
    )

    if os.path.exists(local_out):
        os.remove(local_out)
