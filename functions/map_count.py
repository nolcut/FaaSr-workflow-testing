import json
from collections import Counter

from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_invocation_id,
    faasr_log,
    faasr_put_file,
    faasr_rank,
)


def map_count(folder="mapreduce"):
    """
    MapReduce MAP stage (invoked as ``map(N)`` -> N ranked instances).

    Each ranked instance reads its own text chunk (chunk_<rank>.txt), counts
    how often each word occurs in that chunk, and writes the partial count
    dictionary Y_<rank> to ``<folder>/<invocation_id>/map/Y_<rank>.json``.

    The counting is a generic word count -- it is not tied to any fixed
    vocabulary.
    """
    rank_info = faasr_rank()
    rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    base_path = f"{folder}/{faasr_invocation_id()}"

    # --- Read this rank's chunk ---------------------------------------------
    local_chunk = f"chunk_{rank}.txt"
    faasr_get_file(
        local_file=local_chunk,
        remote_folder=f"{base_path}/chunks",
        remote_file=f"chunk_{rank}.txt",
    )
    with open(local_chunk) as f:
        text = f.read()

    # --- Count word occurrences ---------------------------------------------
    tokens = text.split()
    counts = dict(Counter(tokens))

    # --- Persist partial counts Y_rank --------------------------------------
    out_file = f"Y_{rank}.json"
    with open(out_file, "w") as f:
        json.dump(counts, f)
    faasr_put_file(
        local_file=out_file,
        remote_folder=f"{base_path}/map",
        remote_file=f"Y_{rank}.json",
    )

    faasr_log(
        f"map rank {rank}/{max_rank}: processed {len(tokens)} tokens, "
        f"{len(counts)} distinct words -> {base_path}/map/Y_{rank}.json"
    )
