import csv
import json
import os
from collections import Counter


def reduce_words(folder="MapReduce"):
    """
    Stage 4 of the MapReduce pipeline (the "reduce" phase).

    Because every map_words rank invokes this single action, FaaSr runs
    reduce_words exactly once, only after ALL map invocations have completed
    (it acts as the barrier / merge step). It discovers every partial-count
    file under `folder`/map/, sums the per-word counts across all shards, and
    writes the final aggregated word-count table to
    `folder`/reduce/word_counts.csv (sorted by descending frequency).
    """
    # 1. Discover all map outputs written by the parallel map phase.
    map_prefix = f"{folder}/map"
    listing = faasr_get_folder_list(faasr_prefix=map_prefix)
    map_files = [
        obj for obj in listing
        if obj.endswith(".json") and os.path.basename(obj).startswith("map_")
    ]
    faasr_log(f"reduce_words: found {len(map_files)} map output files")

    # 2. Reduce: accumulate counts across every shard.
    totals = Counter()
    for remote_path in map_files:
        fname = os.path.basename(remote_path)
        faasr_get_file(
            remote_folder=map_prefix,
            remote_file=fname,
            local_folder=".",
            local_file=fname,
        )
        with open(fname) as fh:
            partial = json.load(fh)
        totals.update(partial)

    faasr_log(f"reduce_words: aggregated {len(totals)} unique words")

    # 3. Write the final table sorted by descending count (then word).
    ordered = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    with open("word_counts.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["word", "count"])
        writer.writerows(ordered)

    faasr_put_file(
        local_folder=".",
        local_file="word_counts.csv",
        remote_folder=f"{folder}/reduce",
        remote_file="word_counts.csv",
    )
    faasr_log(f"reduce_words: wrote {folder}/reduce/word_counts.csv")
