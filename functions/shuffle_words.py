import os
import json


def shuffle_words(folder: str, input1: str, output1: str) -> None:
    # Shuffle stage of the MapReduce word-count workflow.
    #
    # Fan-in: this function runs ONCE after all N=3 parallel `map_words`
    # instances finish. It reads every per-chunk word-count object produced by
    # map_words (map_counts_{rank}.json), regroups the partial counts by word,
    # then partitions the discovered vocabulary across exactly M=5 reducers.
    #
    # The vocabulary size is NOT known ahead of time (it comes from a PDF), so
    # the number of distinct words is discovered dynamically from the map
    # outputs. Instead of one reducer per word, the distinct words are sorted
    # deterministically and assigned to reducer ranks by index mod M, so each of
    # the 5 reducers receives its share of the keys. Each output shard holds the
    # reducer's assigned words and, for every word, the list of partial counts
    # contributed across all map outputs.

    # Number of ranked `reduce_counts` successors (fan-out). Fixed by the
    # workflow at 5 -- this function is NOT ranked, so do not use faasr_rank().
    NUM_REDUCERS = 5

    # Derive the map-output filename prefix/suffix from the input template so we
    # can discover map outputs without assuming a fixed count.
    if "{rank}" in input1:
        in_prefix, in_suffix = input1.split("{rank}", 1)
    else:
        in_prefix, in_suffix = input1, ""

    faasr_log(
        f"shuffle_words: discovering map outputs matching '{in_prefix}*{in_suffix}' "
        f"in folder '{folder}'"
    )

    # Discover all map output object keys in the folder (full keys incl. prefix).
    keys = faasr_get_folder_list(prefix=folder)

    map_files = []
    for key in keys:
        base = key.rsplit("/", 1)[-1]
        if base.startswith(in_prefix) and base.endswith(in_suffix) and base != in_prefix + in_suffix:
            map_files.append(base)

    map_files = sorted(set(map_files))

    if not map_files:
        msg = (
            f"shuffle_words: no map outputs matching '{in_prefix}*{in_suffix}' "
            f"found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"shuffle_words: found {len(map_files)} map output(s): {map_files}")

    # Read each map output and collect, for each word, the list of partial counts.
    # dict: word -> list of (source_file, count) so ordering is deterministic.
    partials = {}
    for base in map_files:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"shuffle_words: map output '{base}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r") as f:
            counts = json.load(f)

        if not isinstance(counts, dict):
            msg = (
                f"shuffle_words: map output '{base}' is not a JSON object of "
                f"word->count (got {type(counts).__name__})"
            )
            faasr_log(msg)
            raise ValueError(msg)

        for word, count in counts.items():
            partials.setdefault(word, []).append((base, count))

        faasr_log(
            f"shuffle_words: read '{base}' with {len(counts)} distinct words "
            f"(total {sum(counts.values())})"
        )

    # Deterministic vocabulary order: sorted distinct words.
    vocabulary = sorted(partials.keys())
    faasr_log(
        f"shuffle_words: discovered vocabulary of {len(vocabulary)} distinct words"
    )

    # Deterministic rank-to-keys assignment: word at sorted index j goes to
    # reducer rank (j mod NUM_REDUCERS) + 1. This spreads the discovered
    # vocabulary of unknown size across exactly NUM_REDUCERS reducers.
    assignment = {rank: [] for rank in range(1, NUM_REDUCERS + 1)}
    for j, word in enumerate(vocabulary):
        rank = (j % NUM_REDUCERS) + 1
        assignment[rank].append(word)

    # Emit exactly NUM_REDUCERS shards, keyed by rank 1..M.
    for i in range(1, NUM_REDUCERS + 1):
        assigned_words = assignment[i]

        words_payload = []
        for word in assigned_words:
            contributions = partials[word]
            counts_list = [count for (_src, count) in contributions]
            words_payload.append(
                {
                    "word": word,
                    "partial_counts": counts_list,
                    "num_partials": len(counts_list),
                    "sources": [src for (src, _count) in contributions],
                }
            )

        shard = {
            "rank": i,
            "num_reducers": NUM_REDUCERS,
            "num_words": len(words_payload),
            "words": words_payload,
        }

        remote_out = output1.replace("{rank}", str(i))
        local_out = remote_out
        with open(local_out, "w") as f:
            json.dump(shard, f)

        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(
            f"shuffle_words: reducer rank {i} <- {len(words_payload)} word(s) "
            f"{assigned_words} -> {remote_out}"
        )

    faasr_log(
        f"shuffle_words: complete, partitioned {len(vocabulary)} distinct words "
        f"across {NUM_REDUCERS} reducer shard(s) from {len(map_files)} map output(s)"
    )
