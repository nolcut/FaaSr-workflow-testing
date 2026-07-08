import json
import os


def reduce_count(folder):
    """
    MapReduce REDUCE stage (runs as M concurrent ranked invocations).

    Each ranked reducer is responsible for exactly one word (the one shuffle
    assigned to its rank). It sums that word's flattened partial counts to
    produce the final total occurrence count Z_i.

    Reads : {folder}/{invocation_id}/shuffle/word_{rank}.json
    Writes: {folder}/{invocation_id}/result/result_{rank}.json
            -> {"word": w, "total": total, "partials": [...]}
    """
    rank_info = faasr_rank()
    my_rank = rank_info["rank"]
    max_rank = rank_info["max_rank"]

    inv = faasr_invocation_id()
    base = f"{folder}/{inv}"

    fname = f"word_{my_rank}.json"

    # If there are fewer distinct words than reducers, some ranks have no work.
    listing = faasr_get_folder_list(faasr_prefix=f"{base}/shuffle")
    if not any(os.path.basename(p) == fname for p in listing):
        faasr_log(
            f"reduce rank {my_rank}/{max_rank}: no word group assigned; skipping"
        )
        return

    faasr_get_file(remote_folder=f"{base}/shuffle", remote_file=fname, local_file=fname)
    with open(fname) as f:
        group = json.load(f)

    word = group["word"]
    partials = group["counts"]
    total = sum(partials)

    result = {"word": word, "total": total, "partials": partials}
    local_out = f"result_{my_rank}.json"
    with open(local_out, "w") as f:
        json.dump(result, f)

    faasr_put_file(
        local_file=local_out,
        remote_folder=f"{base}/result",
        remote_file=f"result_{my_rank}.json",
    )

    faasr_log(
        f"reduce rank {my_rank}/{max_rank}: word '{word}' "
        f"total occurrences Z = {total}"
    )
