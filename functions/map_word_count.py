"""
MapReduce - MAP stage (runs concurrently, one invocation per rank).

Each of the N parallel map actions reads its own text chunk
(`<chunk_prefix>_<rank>.txt`), counts how often each word occurs in that
chunk, and writes the partial counts Y_i to S3 as
`<map_prefix>_<rank>.json`.

This function is generic: it counts whatever tokens appear in the chunk
and has no knowledge of the fixed vocabulary.
"""

import json
from collections import Counter


def map_word_count(folder="mapreduce",
                   chunk_prefix="chunk",
                   map_prefix="map_out"):
    # Determine this invocation's position among the N concurrent maps.
    rank_info = faasr_rank()
    my_rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    # ---- Download this rank's chunk of the input text
    chunk_file = f"{chunk_prefix}_{my_rank}.txt"
    faasr_get_file(
        remote_folder=folder,
        remote_file=chunk_file,
        local_folder=".",
        local_file=chunk_file,
    )

    with open(chunk_file, "r") as f:
        text = f.read()

    tokens = text.split()

    # ---- Count word occurrences in this chunk -> Y_i
    counts = dict(Counter(tokens))

    faasr_log(
        f"[map rank {my_rank}/{max_rank}] Counted {len(tokens)} tokens; "
        f"{len(counts)} distinct words: {counts}"
    )

    # ---- Persist the partial counts for the shuffle stage
    out_file = f"{map_prefix}_{my_rank}.json"
    with open(out_file, "w") as f:
        json.dump(counts, f)

    faasr_put_file(
        local_folder=".",
        local_file=out_file,
        remote_folder=folder,
        remote_file=out_file,
    )

    faasr_log(f"[map rank {my_rank}/{max_rank}] Wrote partial counts "
              f"-> {folder}/{out_file}")
