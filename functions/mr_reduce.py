def mr_reduce(folder, group_prefix, result_prefix):
    """
    REDUCE phase (fully generalizable) -- runs as M concurrent ranked invocations.

    Each ranked invocation handles exactly one word group produced by shuffle
    (selected by faasr_rank) and sums its partial counts to yield the total
    occurrences Z_i for that word:

        read  <folder>/<group_prefix><rank>.json  ->  {"word": w, "partials": [...]}
        write <folder>/<result_prefix><rank>.json ->  {"word": w, "count": total}

    Reducers are independent, so all M run in parallel.
    """
    import json

    rank_info = faasr_rank()
    rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    group_name = f"{group_prefix}{rank}.json"
    faasr_get_file(remote_folder=folder, remote_file=group_name,
                   local_folder=".", local_file=group_name)

    with open(group_name) as f:
        group = json.load(f)

    word = group["word"]
    total = sum(int(c) for c in group["partials"])

    result = {"word": word, "count": total}
    out_name = f"{result_prefix}{rank}.json"
    with open(out_name, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_folder=".", local_file=out_name,
                   remote_folder=folder, remote_file=out_name)

    faasr_log(
        f"mr_reduce: rank {rank}/{max_rank} -> word '{word}' total count = {total} "
        f"(written to {folder}/{out_name})"
    )
