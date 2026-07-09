"""FaaSr MapReduce benchmark - map stage (ranked, N parallel invocations).

Generalizable: each ranked map invocation reads its own chunk (selected by
faasr_rank) and counts how often each word occurs in that chunk, producing
the intermediate result Yi.  Emits a JSON object {word: partial_count}.

Invoked as map(N).  InvokeNext: shuffle (fan-in; runs once after all maps).
"""

import json
from collections import Counter


def map_count(folder, chunk_prefix, map_out_prefix):
    """Count word occurrences in this rank's chunk.

    Args:
        folder:         remote S3 folder for all MapReduce artifacts.
        chunk_prefix:   prefix used by split_text; this rank reads
                        "<chunk_prefix>_<rank>.txt".
        map_out_prefix: prefix for this rank's output;
                        "<map_out_prefix>_<rank>.json".
    """
    rank_info = faasr_rank()
    rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    remote_chunk = f"{chunk_prefix}_{rank}.txt"
    faasr_get_file(
        local_file="chunk.txt",
        remote_folder=folder,
        remote_file=remote_chunk,
    )

    with open("chunk.txt") as f:
        tokens = f.read().split()

    # Yi: partial per-word counts for this chunk.
    counts = dict(Counter(tokens))

    local_out = "map_out.json"
    with open(local_out, "w") as f:
        json.dump(counts, f)

    remote_out = f"{map_out_prefix}_{rank}.json"
    faasr_put_file(
        local_file=local_out,
        remote_folder=folder,
        remote_file=remote_out,
    )

    faasr_log(
        f"map_count: rank {rank}/{max_rank} counted {len(tokens)} words "
        f"({len(counts)} distinct) -> {folder}/{remote_out}"
    )
