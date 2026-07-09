"""
MapReduce - REDUCE stage (fully generalizable).

Runs concurrently as M ranks (one per distinct word / shuffle group). Each
rank reads the group file for its index, sums all the partial counts collected
by the shuffle stage, and emits Zi: the total occurrence count for that word.
"""

import json


def reduce_count(group_folder="MapReduce/shuffle",
                 group_prefix="group",
                 reduce_folder="MapReduce/reduce",
                 reduce_prefix="reduce"):

    rank_info = faasr_rank()
    my_rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    group_name = f"{group_prefix}_{my_rank}.json"
    faasr_get_file(remote_folder=group_folder, remote_file=group_name,
                   local_folder=".", local_file=group_name)

    with open(group_name) as fh:
        group = json.load(fh)

    word = group["word"]
    total = sum(int(c) for c in group["counts"])   # Zi

    result = {"word": word, "count": total}
    out_name = f"{reduce_prefix}_{my_rank}.json"
    with open(out_name, "w") as fh:
        json.dump(result, fh)
    faasr_put_file(local_folder=".", local_file=out_name,
                   remote_folder=reduce_folder, remote_file=out_name)

    faasr_log(
        f"[reduce rank {my_rank}/{max_rank}] word='{word}' total={total} "
        f"(from partials {group['counts']}) -> {reduce_folder}/{out_name}."
    )
