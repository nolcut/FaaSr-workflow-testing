import json

from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_invocation_id,
    faasr_log,
    faasr_put_file,
    faasr_rank,
)


def reduce_word(folder="mapreduce"):
    """
    MapReduce REDUCE stage (invoked as ``reduce(M)`` -> M ranked instances).

    Each ranked instance is responsible for exactly one word: reducer of rank r
    handles the r-th word from the shuffle manifest. It reads that word's
    flattened list of partial counts and sums them to produce the total number
    of occurrences Z_r, written to
    ``<folder>/<invocation_id>/reduce/Z_<rank>.json``.

    If there are fewer words than reducers (rank > M), the extra reducer simply
    has no work and exits cleanly -- keeping the stage generalizable.
    """
    rank_info = faasr_rank()
    rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    base_path = f"{folder}/{faasr_invocation_id()}"

    # --- Load the shuffle manifest to learn which word this rank owns --------
    faasr_get_file(
        local_file="words.json",
        remote_folder=f"{base_path}/shuffle",
        remote_file="words.json",
    )
    with open("words.json") as f:
        manifest = json.load(f)
    words = manifest["words"]

    if rank > len(words):
        faasr_log(
            f"reduce rank {rank}/{max_rank}: no word assigned "
            f"(only {len(words)} words present); nothing to do"
        )
        return

    word = words[rank - 1]

    # --- Read the flattened partial counts for this word --------------------
    wf = f"word_{word}.json"
    faasr_get_file(
        local_file=wf,
        remote_folder=f"{base_path}/shuffle",
        remote_file=wf,
    )
    with open(wf) as f:
        data = json.load(f)

    total = sum(data["counts"])

    # --- Persist the reduced result Z_rank ----------------------------------
    result = {"word": word, "total": total}
    out_file = f"Z_{rank}.json"
    with open(out_file, "w") as f:
        json.dump(result, f)
    faasr_put_file(
        local_file=out_file,
        remote_folder=f"{base_path}/reduce",
        remote_file=f"Z_{rank}.json",
    )

    faasr_log(
        f"reduce rank {rank}/{max_rank}: word '{word}' "
        f"total occurrences = {total} -> {base_path}/reduce/Z_{rank}.json"
    )
