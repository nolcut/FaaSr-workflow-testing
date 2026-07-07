import os
import json


def shuffle(folder: str, input1: str, output1: str) -> None:
    # Shuffle stage of the MapReduce word-count benchmark.
    #
    # Fan-in: this function runs ONCE after all N parallel `map_transcription`
    # instances finish. It reads every per-chunk word-count object produced by
    # map (map_counts_{rank}.json), regroups the partial counts by word, and
    # emits one JSON shard per reducer (M=5 shards keyed by {rank}).
    #
    # The discovered vocabulary size will NOT generally match the fixed number
    # of reducers (M=5). We therefore build the sorted vocabulary and assign each
    # word deterministically to a reducer rank via an index->rank partition map
    # (word at sorted index j -> rank (j % M) + 1). This handles any mismatch:
    # fewer words than reducers (some ranks get zero words) or more words than
    # reducers (some ranks get several). Every reducer rank always receives a
    # well-defined shuffle output file, and each file lists the word identity(ies)
    # assigned to that rank together with their partial counts across all map
    # outputs. The mapping is deterministic and generalizable and does NOT assume
    # vocabulary size equals reducer count.

    # Number of ranked `reduce` successors (fan-out). Fixed by the workflow.
    NUM_REDUCERS = 5

    # Derive the map-output filename prefix/suffix from the input template so we
    # can discover the map outputs without assuming a fixed count.
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
        if (
            base.startswith(in_prefix)
            and base.endswith(in_suffix)
            and base != in_prefix + in_suffix
        ):
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

    # Read each map output and collect, for each word, the list of partial counts
    # tagged with their source file so ordering stays deterministic (map_files is
    # already sorted).
    partials = {}
    for base in map_files:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"shuffle: map output '{base}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r", encoding="utf-8") as f:
            counts = json.load(f)

        if not isinstance(counts, dict):
            msg = (
                f"shuffle: map output '{base}' is not a JSON object of "
                f"word->count (got {type(counts).__name__})"
            )
            faasr_log(msg)
            raise ValueError(msg)

        for word, count in counts.items():
            if not isinstance(count, int):
                msg = (
                    f"shuffle: map output '{base}' count for word {word!r} is not "
                    f"an integer: {count!r}"
                )
                faasr_log(msg)
                raise ValueError(msg)
            partials.setdefault(word, []).append((base, count))

        faasr_log(
            f"shuffle: read '{base}' with {len(counts)} distinct words "
            f"(total {sum(counts.values())})"
        )

    # Deterministic sorted vocabulary discovered from the map outputs.
    vocabulary = sorted(partials.keys())
    faasr_log(
        f"shuffle: discovered vocabulary of {len(vocabulary)} distinct words "
        f"across {len(map_files)} map output(s); distributing over "
        f"{NUM_REDUCERS} reducer rank(s)"
    )

    # Partition words across the fixed reducer ranks by sorted index modulo M.
    # This is deterministic and works for any vocabulary size (including sizes
    # that do not match NUM_REDUCERS). rank_words[rank] preserves sorted order.
    rank_words = {i: [] for i in range(1, NUM_REDUCERS + 1)}
    for j, word in enumerate(vocabulary):
        rank = (j % NUM_REDUCERS) + 1
        rank_words[rank].append(word)

    # Emit exactly NUM_REDUCERS shards, one per reducer rank, so every reducer
    # instance always has a well-defined input file.
    for i in range(1, NUM_REDUCERS + 1):
        assigned = rank_words[i]

        assignments = []
        words_map = {}
        for word in assigned:
            contributions = partials[word]
            counts_list = [count for (_src, count) in contributions]
            sources = [src for (src, _count) in contributions]
            assignments.append(
                {
                    "word": word,
                    "partial_counts": counts_list,
                    "num_partials": len(counts_list),
                    "sources": sources,
                }
            )
            words_map[word] = counts_list

        shard = {
            "rank": i,
            "num_reducers": NUM_REDUCERS,
            "vocabulary_size": len(vocabulary),
            "num_words": len(assigned),
            # Primary, generalizable payload: each word assigned to this rank
            # plus its list of partial counts across all map outputs.
            "words": words_map,
            "assignments": assignments,
        }

        # Convenience keys for a single-word rank, matching the simple
        # (word, partial_counts) reducer contract.
        if len(assigned) == 1:
            only = assignments[0]
            shard["word"] = only["word"]
            shard["partial_counts"] = only["partial_counts"]
            shard["num_partials"] = only["num_partials"]
            shard["sources"] = only["sources"]

        remote_out = output1.replace("{rank}", str(i))
        local_out = remote_out
        with open(local_out, "w", encoding="utf-8") as f:
            json.dump(shard, f)

        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(
            f"shuffle: reducer rank {i} <- {len(assigned)} word(s) "
            f"{assigned} -> {remote_out}"
        )

    faasr_log(
        f"shuffle: complete, wrote {NUM_REDUCERS} shard(s) covering a vocabulary "
        f"of {len(vocabulary)} word(s) from {len(map_files)} map output(s)"
    )
