import os
import json


def shuffle_step(folder: str, input1: str, output1: str) -> None:
    # Shuffle stage of the PDF-transcription MapReduce word count.
    #
    # Fan-in: this function runs ONCE after all parallel `map_step` instances
    # finish. It reads every per-chunk word-count object produced by map_step
    # (map_counts_{rank}.json), regroups the partial counts by word, and emits
    # one JSON file per reducer (shuffle_word_{rank}.json), each holding a
    # single word and the list of its partial counts across all map outputs.
    #
    # The vocabulary is unknown and potentially large (real transcribed text),
    # so it is discovered dynamically from the map outputs and NEVER hardcoded.
    # The number of reducers (fan-out) and the rank-to-word assignment are
    # derived deterministically from the sorted vocabulary rather than assuming
    # a fixed M.

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
    # The reducer count IS the discovered vocabulary size (one reducer per
    # distinct word), determined dynamically rather than assuming a fixed M.
    vocabulary = sorted(partials.keys())
    num_reducers = len(vocabulary)
    faasr_log(
        f"shuffle: discovered vocabulary of {num_reducers} distinct words; "
        f"emitting one shuffle shard per word keyed by rank 1..{num_reducers}"
    )

    if num_reducers == 0:
        msg = "shuffle: discovered an empty vocabulary from the map outputs"
        faasr_log(msg)
        raise ValueError(msg)

    # Emit one shard per word, keyed by rank 1..num_reducers, sorted-vocab order.
    for i in range(1, num_reducers + 1):
        word = vocabulary[i - 1]
        contributions = partials[word]
        counts_list = [int(count) for (_src, count) in contributions]

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
        f"shuffle: complete, wrote {num_reducers} per-word shards from "
        f"{len(map_files)} map output(s)"
    )
