import csv
from collections import Counter


def mapper(splits_folder="MapReduce/splits", map_folder="MapReduce/map_out"):
    """MAP stage of the MapReduce word-count.

    Runs once per rank (concurrently). Each invocation processes the shard that
    matches its rank and emits partial (word, count) pairs.

    Reads:  {splits_folder}/part_{rank}.txt
    Writes: {map_folder}/counts_{rank}.csv
    """
    # Determine which shard this concurrent invocation is responsible for
    rank_info = faasr_rank()
    rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    shard_file = f"part_{rank}.txt"

    # Download this rank's shard
    faasr_get_file(
        remote_folder=splits_folder,
        remote_file=shard_file,
        local_folder=".",
        local_file=shard_file,
    )

    with open(shard_file, "r", encoding="utf-8") as fh:
        words = [w for w in fh.read().splitlines() if w.strip()]

    # Local (partial) word count for this shard
    counts = Counter(words)

    out_file = f"counts_{rank}.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["word", "count"])
        for word, count in counts.items():
            writer.writerow([word, count])

    # Persist the partial counts for the reducer to aggregate
    faasr_put_file(
        local_folder=".",
        local_file=out_file,
        remote_folder=map_folder,
        remote_file=out_file,
    )

    faasr_log(
        f"mapper: rank {rank}/{max_rank} counted {len(words)} words "
        f"({len(counts)} unique) -> {map_folder}/{out_file}"
    )
