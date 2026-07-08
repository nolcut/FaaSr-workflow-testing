import re
import json


def map_wordcount(folder, input_prefix, output_prefix):
    """
    Stage 3 - Map (runs concurrently, once per rank).

    This function is invoked as a ranked action (e.g. "map(3)"), so FaaSr runs
    `max_rank` concurrent copies, each with a distinct `rank` in 1..max_rank.
    Each copy reads its own shard `<input_prefix>_<rank>.txt`, tokenizes it into
    lowercase words, and emits a partial word-count map as JSON.

    Emits: <output_prefix>_<rank>.json  =  {"word": count, ...}

    Arguments:
      folder        : S3 folder for shard input and map output.
      input_prefix  : shard prefix produced by split (e.g. "split").
      output_prefix : prefix for this map's partial counts (e.g. "map_out").
    """
    rank_info = faasr_rank()
    my_rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    shard_name = f"{input_prefix}_{my_rank}.txt"
    faasr_get_file(remote_folder=folder, remote_file=shard_name, local_file=shard_name)

    with open(shard_name, "r", encoding="utf-8") as f:
        text = f.read().lower()

    # Tokenize on runs of alphabetic characters (apostrophes kept for words
    # like "don't"). This does not depend on knowing the word count in advance.
    words = re.findall(r"[a-z']+", text)

    counts = {}
    for w in words:
        w = w.strip("'")
        if w:
            counts[w] = counts.get(w, 0) + 1

    out_name = f"{output_prefix}_{my_rank}.json"
    with open(out_name, "w", encoding="utf-8") as f:
        json.dump(counts, f)

    faasr_put_file(local_file=out_name, remote_folder=folder, remote_file=out_name)

    faasr_log(
        f"map_wordcount: rank {my_rank}/{max_rank} counted {len(words)} tokens "
        f"({len(counts)} unique) -> {folder}/{out_name}"
    )
