import json
import os


def shuffle(folder: str, input1: str, output1: str) -> None:
    # Deterministic vocabulary / rank ordering shared across the MapReduce
    # benchmark (matches split's vocabulary). Reducer rank i (1..M) handles
    # vocabulary[i-1].
    vocabulary = ["cat", "dog", "bird", "horse", "pig"]
    M = len(vocabulary)  # number of distinct words / reducers (5)

    # Prefix of the per-map partial-count files (input1 without the {rank}
    # placeholder), used to identify only the map outputs in the folder.
    in_prefix = input1.split("{rank}")[0]  # "map_partial_counts_"

    faasr_log(
        f"shuffle: discovering map partial-count files with prefix "
        f"'{in_prefix}' in folder '{folder}'"
    )

    # Discover ALL per-rank map outputs (fan-in from N ranked map instances).
    all_names = faasr_get_folder_list(prefix=folder)
    map_files = sorted(
        name for name in all_names
        if name.rsplit("/", 1)[-1].startswith(in_prefix)
        and name.rsplit("/", 1)[-1].endswith(".json")
    )

    if not map_files:
        msg = (
            f"shuffle: no map partial-count files found with prefix "
            f"'{in_prefix}' in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"shuffle: found {len(map_files)} map output(s): {map_files}")

    # Group all partial counts by word (flatten the array Yi).
    grouped = {w: [] for w in vocabulary}

    for name in map_files:
        basename = name.rsplit("/", 1)[-1]
        local_in = basename
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=basename)

        with open(local_in, "r") as f:
            partial = json.load(f)

        if not isinstance(partial, dict):
            raise ValueError(
                f"shuffle: expected a JSON object of word->count in {basename}, "
                f"got {type(partial).__name__}"
            )

        for word, count in partial.items():
            if word not in grouped:
                # A word appeared that is not in the known vocabulary — this
                # indicates upstream data does not match the benchmark spec.
                raise ValueError(
                    f"shuffle: unexpected word '{word}' in {basename}; "
                    f"vocabulary is {vocabulary}"
                )
            grouped[word].append(count)

        if os.path.exists(local_in):
            os.remove(local_in)

    faasr_log(f"shuffle: grouped partial counts by word: {grouped}")

    # Emit one output shard per distinct word (M=5), numbered by reducer rank.
    # The rank -> word mapping is deterministic (vocabulary ordering).
    for i in range(1, M + 1):
        word = vocabulary[i - 1]
        shard = {"word": word, "partial_counts": grouped[word]}

        local_out = f"shuffle_word_shard_{i}.json"
        with open(local_out, "w") as f:
            json.dump(shard, f)

        remote_out = output1.replace("{rank}", str(i))
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(
            f"shuffle: wrote shard rank={i} word='{word}' -> {remote_out} "
            f"with {len(grouped[word])} partial counts"
        )

        if os.path.exists(local_out):
            os.remove(local_out)

    faasr_log(f"shuffle: completed, wrote {M} word shards")
