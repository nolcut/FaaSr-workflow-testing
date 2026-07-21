"""FaaSr MapReduce benchmark - reduce stage (ranked, M parallel invocations).

Generalizable: each ranked reducer owns exactly one word's shard produced by
shuffle (selected by faasr_rank), sums the partial counts, and writes the
total occurrences Zi for that word.

Invoked as reduce(M).  Terminal stage (no InvokeNext).
"""

import json


def reduce_count(folder, shuffle_prefix, reduce_out_prefix):
    """Sum the partial counts for this rank's word.

    Args:
        folder:            remote S3 folder for all MapReduce artifacts.
        shuffle_prefix:    prefix used by shuffle_flatten; this rank reads
                           "<shuffle_prefix>_<rank>.json".
        reduce_out_prefix: prefix for this rank's output;
                           "<reduce_out_prefix>_<rank>.json".
    """
    rank_info = faasr_rank()
    rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    remote_shard = f"{shuffle_prefix}_{rank}.json"
    faasr_get_file(
        local_file="shuffle.json",
        remote_folder=folder,
        remote_file=remote_shard,
    )

    with open("shuffle.json") as f:
        payload = json.load(f)

    word = payload["word"]
    total = sum(payload["counts"])

    # Zi: final total occurrences for this word.
    result = {"word": word, "total": total}
    local_out = "reduce_out.json"
    with open(local_out, "w") as f:
        json.dump(result, f)

    remote_out = f"{reduce_out_prefix}_{rank}.json"
    faasr_put_file(
        local_file=local_out,
        remote_folder=folder,
        remote_file=remote_out,
    )

    faasr_log(
        f"reduce_count: rank {rank}/{max_rank} word '{word}' "
        f"total={total} -> {folder}/{remote_out}"
    )
