import json
from collections import Counter


def map_words(folder="MapReduce"):
    """
    Stage 3 of the MapReduce pipeline (the "map" phase).

    This action is fanned out into N concurrent invocations via the
    map_words(N) rank notation in the workflow JSON. Each invocation uses its
    unique rank to read exactly one dataset shard (splits/part_<rank>.txt),
    computes the local word-count for that shard, and writes the partial result
    to `folder`/map/map_<rank>.json. The downstream reduce_words action merges
    all of these partial counts.
    """
    # 1. Determine which shard this invocation is responsible for.
    rank_info = faasr_rank()
    my_rank = rank_info["rank"]
    max_rank = rank_info["max_rank"]
    faasr_log(f"map_words: starting rank {my_rank} of {max_rank}")

    part_file = f"part_{my_rank}.txt"

    # 2. Download this rank's shard.
    faasr_get_file(
        remote_folder=f"{folder}/splits",
        remote_file=part_file,
        local_folder=".",
        local_file=part_file,
    )

    with open(part_file) as fh:
        words = fh.read().split()

    # 3. Map: emit (word, count) pairs for this shard.
    counts = Counter(words)
    faasr_log(
        f"map_words: rank {my_rank} counted {len(words)} words, "
        f"{len(counts)} unique"
    )

    # 4. Persist the partial count as JSON for the reduce phase.
    out_local = f"map_{my_rank}.json"
    with open(out_local, "w") as fh:
        json.dump(dict(counts), fh)

    faasr_put_file(
        local_folder=".",
        local_file=out_local,
        remote_folder=f"{folder}/map",
        remote_file=f"map_{my_rank}.json",
    )
    faasr_log(f"map_words: rank {my_rank} wrote {folder}/map/map_{my_rank}.json")
