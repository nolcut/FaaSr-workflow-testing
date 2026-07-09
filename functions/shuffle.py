import json
import os


def shuffle(folder: str, input1: str, output1: str) -> None:
    # Fan-in: read ALL per-mapper partial-count files. We do NOT assume a fixed
    # mapper count — discover the files by listing the folder and matching the
    # input filename pattern (prefix + {rank} + suffix).
    marker = "{rank}"
    if marker in input1:
        in_prefix, in_suffix = input1.split(marker, 1)
    else:
        in_prefix, in_suffix = input1, ""

    keys = faasr_get_folder_list(prefix=folder)
    mapper_basenames = []
    for key in keys:
        base = key.rsplit("/", 1)[-1]
        if base.startswith(in_prefix) and base.endswith(in_suffix) and base != in_prefix + in_suffix:
            mapper_basenames.append(base)
    mapper_basenames = sorted(set(mapper_basenames))

    if not mapper_basenames:
        msg = f"shuffle: no mapper result files matching '{input1}' found in folder '{folder}'"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"shuffle: reading {len(mapper_basenames)} mapper result files: {mapper_basenames}")

    # Regroup partial counts by word: word -> list of per-mapper partial counts.
    word_to_counts = {}
    for base in mapper_basenames:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)
        with open(local_in) as f:
            partial = json.load(f)
        if not isinstance(partial, dict):
            msg = f"shuffle: expected a JSON word->count object in '{base}', got {type(partial).__name__}"
            faasr_log(msg)
            raise ValueError(msg)
        for word, count in partial.items():
            word_to_counts.setdefault(word, []).append(count)
        if os.path.exists(local_in):
            os.remove(local_in)

    # Collect all distinct words and sort deterministically. The r-th sorted word
    # is assigned to reducer rank r. Fully derived at runtime — no hardcoded vocab.
    sorted_words = sorted(word_to_counts.keys())
    faasr_log(f"shuffle: {len(sorted_words)} distinct words (sorted): {sorted_words}")

    # Fan-out to ranked successor reduce_count runs as exactly 5 parallel instances.
    # THIS function is NOT ranked — do not call faasr_rank(); use the literal count.
    n_reducers = 5

    for r in range(1, n_reducers + 1):
        # The word assigned to reducer rank r is the r-th sorted distinct word
        # (1-indexed -> index r-1). If there are fewer distinct words than
        # reducers, the surplus reducers get an empty group.
        if r - 1 < len(sorted_words):
            word = sorted_words[r - 1]
            counts = word_to_counts[word]
        else:
            word = None
            counts = []

        group = {
            "words": sorted_words,      # full sorted distinct vocabulary (rank->word)
            "word": word,               # word assigned to this reducer rank
            "partial_counts": counts,   # per-mapper partial counts for the assigned word
        }

        local_out = f"shuffle_group_{r}.json"
        with open(local_out, "w") as f:
            json.dump(group, f)

        remote_out = output1.replace(marker, str(r))
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(
            f"shuffle: reducer rank {r} -> word '{word}', "
            f"{len(counts)} partial counts, wrote '{remote_out}'"
        )

        if os.path.exists(local_out):
            os.remove(local_out)
