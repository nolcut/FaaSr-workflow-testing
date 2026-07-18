import json
import os


def shuffle(folder: str, input1: str, output1: str, output2: str) -> None:
    # Number of parallel reducer instances (ranked successor `reduce` runs x5).
    # THIS function is NOT ranked, so the count is the literal fan-out from the
    # spec, NOT derived from faasr_rank().
    num_reducers = 5

    # --- Fan-in from ranked predecessor `map` (x3): discover ALL of its
    # per-rank partial_counts files without assuming a fixed count. ---
    prefix = input1.split("{", 1)[0]  # "partial_counts_"
    all_names = faasr_get_folder_list(prefix=folder)
    partial_files = sorted(
        name for name in all_names
        if name.rsplit("/", 1)[-1].startswith(prefix)
        and name.rsplit("/", 1)[-1].endswith(".json")
    )

    if not partial_files:
        faasr_log(f"[shuffle] no files matching '{prefix}*.json' found under {folder}")
        raise RuntimeError(
            f"shuffle: found no partial-count inputs under folder '{folder}' "
            f"(prefix '{prefix}')"
        )

    faasr_log(f"[shuffle] found {len(partial_files)} mapper outputs: {partial_files}")

    # --- Aggregate all (word, count) pairs and group them by word. ---
    grouped = {}  # word -> list of partial counts across all mappers
    for name in partial_files:
        base = name.rsplit("/", 1)[-1]
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)
        with open(local_in, "r") as f:
            partial = json.load(f)
        if not isinstance(partial, dict):
            raise ValueError(
                f"Expected a JSON object (word->count) in {base}, "
                f"got {type(partial).__name__}"
            )
        for word, count in partial.items():
            grouped.setdefault(word, []).append(count)
        try:
            os.remove(local_in)
        except OSError:
            pass

    # Deterministic, stable ordering of distinct words -> reducer ranks.
    distinct_words = sorted(grouped.keys())
    faasr_log(
        f"[shuffle] {len(distinct_words)} distinct words: {distinct_words}"
    )

    # The number of distinct words (M) must match the reducer fan-out so every
    # word is handled by exactly one reducer and no reducer is left without a key.
    if len(distinct_words) != num_reducers:
        raise RuntimeError(
            f"shuffle: number of distinct words ({len(distinct_words)}) does not "
            f"match the reducer fan-out ({num_reducers}); cannot build a 1:1 "
            f"rank->word mapping. Words: {distinct_words}"
        )

    # --- Build and persist the stable rank->word mapping. ---
    rank_word_map = {str(i): distinct_words[i - 1] for i in range(1, num_reducers + 1)}
    local_map = "rank_word_map.json"
    with open(local_map, "w") as f:
        json.dump(rank_word_map, f)
    faasr_put_file(local_file=local_map, remote_folder=folder, remote_file=output2)
    faasr_log(f"[shuffle] wrote rank->word map to {folder}/{output2}: {rank_word_map}")
    try:
        os.remove(local_map)
    except OSError:
        pass

    # --- Emit one output file per distinct word, keyed by reducer rank. ---
    for i in range(1, num_reducers + 1):
        word = rank_word_map[str(i)]
        counts = grouped[word]
        local_out = f"word_counts_{i}.json"
        with open(local_out, "w") as f:
            json.dump(counts, f)
        remote_out = output1.replace("{rank}", str(i))
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(
            f"[shuffle] rank {i} -> '{word}': partial counts {counts} "
            f"written to {folder}/{remote_out}"
        )
        try:
            os.remove(local_out)
        except OSError:
            pass
