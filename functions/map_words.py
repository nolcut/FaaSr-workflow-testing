import csv
from collections import Counter


def map_words(folder="MapReduce", part_prefix="part", map_prefix="map_out"):
    """MAP step (rank-based, runs concurrently N times).

    Each rank r processes exactly one shard produced by split_dataset and emits
    a per-shard word count.

    Reads  : <folder>/<part_prefix>_<rank>.txt
    Writes : <folder>/<map_prefix>_<rank>.csv   (columns: word,count)
    """
    # Determine this invocation's rank within the concurrent group.
    rank_info = faasr_rank()
    rank = rank_info["rank"]
    max_rank = rank_info["max_rank"]

    part_file = f"{part_prefix}_{rank}.txt"
    faasr_get_file(remote_folder=folder, remote_file=part_file,
                   local_folder=".", local_file=part_file)

    with open(part_file, "r", encoding="utf-8") as f:
        words = [w for w in f.read().splitlines() if w.strip()]

    # Local (per-shard) word count -- the "map" output.
    counts = Counter(words)

    map_file = f"{map_prefix}_{rank}.csv"
    with open(map_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "count"])
        for word, count in counts.items():
            writer.writerow([word, count])

    faasr_put_file(local_folder=".", local_file=map_file,
                   remote_folder=folder, remote_file=map_file)

    faasr_log(f"map_words: rank {rank}/{max_rank} counted {len(words)} words "
              f"({len(counts)} unique) -> {folder}/{map_file}")
