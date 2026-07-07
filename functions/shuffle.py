import json
import os


def shuffle(folder: str, input1: str, output1: str) -> None:
    # Fixed vocabulary (M = 5 distinct words) for the word-count benchmark.
    # Rank -> word mapping is deterministic via sorted word order.
    WORDS = ["cat", "dog", "bird", "horse", "pig"]
    SORTED_WORDS = sorted(WORDS)  # ['bird', 'cat', 'dog', 'horse', 'pig']
    M = len(SORTED_WORDS)

    # Derive the filename prefix/suffix used by the ranked `map` predecessor so
    # we can discover ALL of its per-rank outputs regardless of how many ran.
    if "{rank}" not in input1:
        raise ValueError(
            f"shuffle: expected '{{rank}}' template in input1, got {input1!r}"
        )
    in_prefix, in_suffix = input1.split("{rank}", 1)  # 'partial_counts_', '.json'

    faasr_log(
        f"shuffle: discovering map outputs in folder '{folder}' "
        f"matching '{in_prefix}*{in_suffix}'"
    )

    # Discover every partial-counts file produced by the map stage. FaaSr returns
    # FULL object keys including the folder prefix; strip to the basename.
    all_names = faasr_get_folder_list(prefix=folder)
    partial_names = []
    for name in all_names:
        base = name.rsplit("/", 1)[-1]
        if base.startswith(in_prefix) and base.endswith(in_suffix):
            partial_names.append(base)
    partial_names = sorted(set(partial_names))

    if not partial_names:
        msg = (
            f"shuffle: no map outputs found matching "
            f"'{in_prefix}*{in_suffix}' in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"shuffle: found {len(partial_names)} map outputs: {partial_names}")

    # Read each mapper's partial word-count map and regroup by word.
    grouped = {w: [] for w in SORTED_WORDS}
    for base in partial_names:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)

        with open(local_in, "r") as f:
            counts = json.load(f)

        if not isinstance(counts, dict):
            raise ValueError(
                f"shuffle: expected a JSON object (word -> count) in {base}, "
                f"got {type(counts).__name__}"
            )

        for word, count in counts.items():
            if word not in grouped:
                raise ValueError(
                    f"shuffle: encountered word '{word}' in {base} not in the "
                    f"fixed vocabulary {SORTED_WORDS}"
                )
            grouped[word].append(count)

        faasr_log(f"shuffle: merged partial counts from {base}: {counts}")

        if os.path.exists(local_in):
            os.remove(local_in)

    # Emit exactly M=5 per-word group files, one per downstream reducer instance.
    # Rank i (1..M) maps to the i-th word in sorted order.
    for i in range(1, M + 1):
        word = SORTED_WORDS[i - 1]
        group = {"word": word, "counts": grouped[word]}

        out_name = output1.replace("{rank}", str(i))
        local_out = f"word_group_{i}.json"
        with open(local_out, "w") as f:
            json.dump(group, f)

        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=out_name)
        faasr_log(
            f"shuffle: wrote group for word '{word}' "
            f"({len(group['counts'])} partial counts) to {out_name}"
        )

        if os.path.exists(local_out):
            os.remove(local_out)

    faasr_log("shuffle: complete")
