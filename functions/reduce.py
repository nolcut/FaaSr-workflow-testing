import os
import json


def reduce(folder: str, input1: str, output1: str) -> None:
    # Reduce stage of the MapReduce word-count benchmark.
    #
    # Runs as M=5 parallel ranked instances. Each reducer reads the flattened
    # shuffle output assigned to its rank (shuffle_word_{rank}.json), which holds
    # a single word plus the list of that word's partial counts aggregated across
    # all N map outputs. The reducer sums those partial counts to yield Zi, the
    # final total occurrences of its word, and writes it to reduce_total_{rank}.json.

    r = faasr_rank()
    rank = r["rank"]

    remote_in = input1.replace("{rank}", str(rank))
    remote_out = output1.replace("{rank}", str(rank))

    local_in = remote_in
    faasr_log(f"reduce: rank {rank} fetching shuffle shard '{remote_in}' from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"reduce: shuffle shard '{remote_in}' is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    with open(local_in, "r") as f:
        shard = json.load(f)

    if not isinstance(shard, dict) or "word" not in shard or "partial_counts" not in shard:
        msg = (
            f"reduce: shuffle shard '{remote_in}' has an unexpected structure "
            f"(expected object with 'word' and 'partial_counts'): {shard!r}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    word = shard["word"]
    partial_counts = shard["partial_counts"]

    if not isinstance(partial_counts, list) or not all(isinstance(c, int) for c in partial_counts):
        msg = (
            f"reduce: shuffle shard '{remote_in}' 'partial_counts' is not a list "
            f"of integers: {partial_counts!r}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    total = sum(partial_counts)

    faasr_log(
        f"reduce: rank {rank} word '{word}' summed {len(partial_counts)} partial "
        f"counts {partial_counts} -> total {total}"
    )

    result = {
        "word": word,
        "total": total,
        "num_partials": len(partial_counts),
        "partial_counts": partial_counts,
    }

    local_out = remote_out
    with open(local_out, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(f"reduce: rank {rank} wrote final total for '{word}' -> {remote_out}")
