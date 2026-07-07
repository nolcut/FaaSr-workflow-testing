import os
import json


def shuffle(folder: str, input1: str, output1: str) -> None:
    # Shuffle stage of the MapReduce word-count benchmark.
    #
    # Fan-in: this function runs ONCE after all N=3 parallel `map` instances
    # finish. It reads every per-chunk word-count object produced by map
    # (map_counts_{rank}.json), regroups the partial counts by word, and emits
    # one JSON file per reducer (M=5 shards keyed by {rank}), each holding a
    # single word and the list of its partial counts across all map outputs.

    # Number of ranked `reduce` successors (fan-out). Fixed by the workflow.
    NUM_REDUCERS = 5

    # Derive the map-output filename prefix/suffix from the input template so
    # we can discover map outputs without assuming a fixed count.
    if "{rank}" in input1:
        in_prefix, in_suffix = input1.split("{rank}", 1)
    else:
        in_prefix, in_suffix = input1, ""

    faasr_log(
        f"shuffle: discovering map outputs matching '{in_prefix}*{in_suffix}' "
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
            f"shuffle: no map outputs matching '{in_prefix}*{in_suffix}' found "
            f"in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"shuffle: found {len(map_files)} map output(s): {map_files}")

    # Read each map output and collect, for each word, the list of partial counts.
    # dict: word -> list of (source_file, count) so ordering is deterministic.
    partials = {}
    for base in map_files:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"shuffle: map output '{base}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r") as f:
            counts = json.load(f)

        if not isinstance(counts, dict):
            msg = (
                f"shuffle: map output '{base}' is not a JSON object of "
                f"word->count (got {type(counts).__name__})"
            )
            faasr_log(msg)
            raise ValueError(msg)

        for word, count in counts.items():
            partials.setdefault(word, []).append((base, count))

        faasr_log(
            f"shuffle: read '{base}' with {len(counts)} distinct words "
            f"(total {sum(counts.values())})"
        )

    # Deterministic rank-to-word assignment: sorted vocabulary order.
    vocabulary = sorted(partials.keys())
    faasr_log(
        f"shuffle: discovered vocabulary of {len(vocabulary)} distinct words: "
        f"{vocabulary}"
    )

    if len(vocabulary) != NUM_REDUCERS:
        msg = (
            f"shuffle: discovered vocabulary size {len(vocabulary)} does not "
            f"match the number of reducers ({NUM_REDUCERS}); cannot assign one "
            f"word per reducer. Vocabulary: {vocabulary}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Emit exactly NUM_REDUCERS shards, one per word, keyed by rank 1..M.
    for i in range(1, NUM_REDUCERS + 1):
        word = vocabulary[i - 1]
        contributions = partials[word]
        counts_list = [count for (_src, count) in contributions]

        shard = {
            "word": word,
            "partial_counts": counts_list,
            "num_partials": len(counts_list),
            "sources": [src for (src, _count) in contributions],
        }

        remote_out = output1.replace("{rank}", str(i))
        local_out = remote_out
        with open(local_out, "w") as f:
            json.dump(shard, f)

        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(
            f"shuffle: reducer rank {i} <- word '{word}' with "
            f"{len(counts_list)} partial counts {counts_list} -> {remote_out}"
        )

    faasr_log(
        f"shuffle: complete, wrote {NUM_REDUCERS} per-word shards from "
        f"{len(map_files)} map output(s)"
    )
