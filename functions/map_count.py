import json
from collections import Counter


def map_count(folder):
    """
    MapReduce MAP stage (runs as N concurrent ranked invocations).

    Each ranked worker reads its own text chunk and counts how often every
    word occurs in that chunk, producing the partial result Y_i.

    Reads : {folder}/{invocation_id}/input/chunk_{rank}.txt
    Writes: {folder}/{invocation_id}/map/map_out_{rank}.json
            -> {"rank": r, "counts": {word: count, ...}}

    The counting is fully generalizable: it counts whatever whitespace-separated
    tokens appear in the chunk, not a fixed vocabulary.
    """
    rank_info = faasr_rank()
    my_rank = rank_info["rank"]
    max_rank = rank_info["max_rank"]

    inv = faasr_invocation_id()
    base = f"{folder}/{inv}"

    local_in = f"chunk_{my_rank}.txt"
    faasr_get_file(
        remote_folder=f"{base}/input",
        remote_file=f"chunk_{my_rank}.txt",
        local_file=local_in,
    )

    with open(local_in) as f:
        text = f.read()

    words = text.split()
    counts = dict(Counter(words))

    result = {"rank": my_rank, "counts": counts}
    local_out = f"map_out_{my_rank}.json"
    with open(local_out, "w") as f:
        json.dump(result, f)

    faasr_put_file(
        local_file=local_out,
        remote_folder=f"{base}/map",
        remote_file=f"map_out_{my_rank}.json",
    )

    faasr_log(
        f"map rank {my_rank}/{max_rank}: counted {len(words)} tokens, "
        f"{len(counts)} distinct words -> map_out_{my_rank}.json"
    )
