def mr_map(folder, batch_prefix, map_prefix):
    """
    MAP phase (fully generalizable) -- runs as N concurrent ranked invocations.

    Each ranked invocation reads its own batch (selected by faasr_rank) and
    counts how often every word occurs in that chunk, producing a partial
    count Y_i written as JSON:
        <folder>/<map_prefix><rank>.json  ->  {"word": count, ...}

    Makes no assumption about which words appear.
    """
    import json
    from collections import Counter

    rank_info = faasr_rank()
    rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    batch_name = f"{batch_prefix}{rank}.txt"
    faasr_get_file(remote_folder=folder, remote_file=batch_name,
                   local_folder=".", local_file=batch_name)

    with open(batch_name) as f:
        tokens = f.read().split()

    counts = dict(Counter(tokens))

    out_name = f"{map_prefix}{rank}.json"
    with open(out_name, "w") as f:
        json.dump(counts, f)

    faasr_put_file(local_folder=".", local_file=out_name,
                   remote_folder=folder, remote_file=out_name)

    faasr_log(
        f"mr_map: rank {rank}/{max_rank} counted {len(tokens)} tokens "
        f"({len(counts)} distinct) -> {folder}/{out_name}"
    )
