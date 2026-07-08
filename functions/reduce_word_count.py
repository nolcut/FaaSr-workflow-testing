"""
MapReduce - REDUCE stage (runs concurrently, one invocation per rank).

Each of the M parallel reducers reads its own word's partial counts
(`<reduce_prefix>_<rank>.json`), sums them to obtain the total number of
occurrences of that word, and writes the final result Z_i to S3 as
`<result_prefix>_<rank>.json`.

Like the map stage, this function is generic and word-agnostic.
"""

import json


def reduce_word_count(folder="mapreduce",
                      reduce_prefix="reduce_in",
                      result_prefix="reduce_out"):
    # Determine this reducer's position among the M concurrent reduces.
    rank_info = faasr_rank()
    my_rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    # ---- Download this rank's word group
    in_file = f"{reduce_prefix}_{my_rank}.json"
    faasr_get_file(
        remote_folder=folder,
        remote_file=in_file,
        local_folder=".",
        local_file=in_file,
    )

    with open(in_file, "r") as f:
        payload = json.load(f)

    word = payload["word"]
    partial_counts = payload["partial_counts"]

    # ---- Sum the partial counts -> total occurrences (Z_i)
    total = sum(int(c) for c in partial_counts)

    result = {"word": word, "total": total}

    faasr_log(
        f"[reduce rank {my_rank}/{max_rank}] word='{word}' "
        f"partials={partial_counts} -> total={total}"
    )

    # ---- Persist the final result
    out_file = f"{result_prefix}_{my_rank}.json"
    with open(out_file, "w") as f:
        json.dump(result, f)

    faasr_put_file(
        local_folder=".",
        local_file=out_file,
        remote_folder=folder,
        remote_file=out_file,
    )

    faasr_log(f"[reduce rank {my_rank}/{max_rank}] Wrote result "
              f"-> {folder}/{out_file}")
