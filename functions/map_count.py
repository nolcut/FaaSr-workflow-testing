"""
MapReduce - MAP stage (fully generalizable).

Runs concurrently as N ranks (one per chunk produced by the split stage).
Each rank uses faasr_rank() to discover its identity, reads its own chunk,
and emits Yi: a partial word-count dictionary for that chunk.

No benchmark-specific knowledge (word list, W, N) is baked in - the word
set is discovered directly from the text, and N comes from faasr_rank().
"""

import json
from collections import Counter


def map_count(chunks_folder="MapReduce/chunks",
              chunk_prefix="chunk",
              map_folder="MapReduce/map",
              map_prefix="map"):

    rank_info = faasr_rank()
    my_rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    chunk_name = f"{chunk_prefix}_{my_rank}.txt"
    local_chunk = chunk_name
    faasr_get_file(remote_folder=chunks_folder, remote_file=chunk_name,
                   local_folder=".", local_file=local_chunk)

    with open(local_chunk) as fh:
        text = fh.read()

    # Tokenize on whitespace; count occurrences of every word in this chunk.
    tokens = text.split()
    counts = Counter(tokens)
    partial = dict(counts)   # Yi : {word -> partial count}

    out_name = f"{map_prefix}_{my_rank}.json"
    with open(out_name, "w") as fh:
        json.dump(partial, fh)
    faasr_put_file(local_folder=".", local_file=out_name,
                   remote_folder=map_folder, remote_file=out_name)

    faasr_log(
        f"[map rank {my_rank}/{max_rank}] Counted {len(tokens)} tokens over "
        f"{len(partial)} distinct words -> {map_folder}/{out_name}."
    )
