import os
import json


def shuffle(folder: str, input1: str, output1: str) -> None:
    # Number of reducers (M). This function feeds the ranked successor
    # reduce_word_count, which runs as exactly 5 parallel instances, so we
    # must emit exactly 5 output shards. This function is NOT itself ranked,
    # so we do NOT call faasr_rank(); the count is the literal fan-out value.
    num_reducers = 5

    # Fan-in from the ranked predecessor map_word_count: discover ALL of its
    # per-rank outputs (do not assume a fixed count, do not use boto3).
    # input1 is a pattern like "map_counts_{rank}.json"; match basenames by
    # its literal prefix/suffix around the {rank} placeholder.
    prefix_part, suffix_part = input1.split("{rank}")
    all_keys = faasr_get_folder_list(prefix=folder)
    map_files = []
    for key in all_keys:
        base = key.rsplit("/", 1)[-1]
        if base.startswith(prefix_part) and base.endswith(suffix_part) and base != prefix_part + suffix_part:
            map_files.append(base)
    map_files = sorted(set(map_files))

    if not map_files:
        faasr_log(
            f"shuffle: found no map outputs matching '{input1}' under {folder}."
        )
        raise ValueError("No map_word_count outputs found to shuffle")

    faasr_log(f"shuffle: found {len(map_files)} map outputs: {map_files}")

    # Flatten the per-map partial counts and regroup by word: each word maps
    # to the list of its partial counts collected from every map output.
    grouped = {}
    for base in map_files:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)
        with open(local_in, "r") as f:
            content = f.read()
        if not content.strip():
            faasr_log(f"shuffle: map output {base} is empty or missing.")
            raise ValueError(f"Map output {base} is empty")
        partial = json.loads(content)
        if not isinstance(partial, dict):
            faasr_log(
                f"shuffle: expected a JSON object (word->count) in {base}, "
                f"got {type(partial).__name__}."
            )
            raise ValueError(f"Map output {base} is not a word->count object")
        for word, count in partial.items():
            grouped.setdefault(word, []).append(count)
        if os.path.exists(local_in):
            os.remove(local_in)

    # Discover the full vocabulary as the sorted union of all words, and assign
    # words to reducers deterministically by sorted order (reducer of a given
    # rank always handles the same word). Generalizable to any vocabulary size.
    vocabulary = sorted(grouped.keys())
    faasr_log(
        f"shuffle: regrouped {len(vocabulary)} distinct words {vocabulary} "
        f"across {num_reducers} reducers."
    )

    for i in range(1, num_reducers + 1):
        # Reducer i (1-based) handles the (i-1)-th sorted word, if present.
        if i - 1 < len(vocabulary):
            word = vocabulary[i - 1]
            counts = grouped[word]
        else:
            # Fewer distinct words than reducers: emit an empty group so the
            # ranked successor still has an input for every rank.
            word = None
            counts = []

        group = {"word": word, "counts": counts}
        local_out = f"shuffle_group_{i}.json"
        with open(local_out, "w") as f:
            json.dump(group, f)

        remote_out = output1.replace("{rank}", str(i))
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(
            f"shuffle: reducer {i} assigned word={word!r} with partial counts "
            f"{counts} -> {folder}/{remote_out}."
        )
        if os.path.exists(local_out):
            os.remove(local_out)
