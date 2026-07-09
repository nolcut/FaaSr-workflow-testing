import json
import os


def shuffle(folder: str, input1: str, output1: str) -> None:
    # Fan-in from ranked predecessor map_word_count (x3). Discover ALL of its
    # per-rank outputs at runtime (do not assume a fixed count, no boto3).
    prefix_part, suffix_part = input1.split("{rank}")  # "map_result_", ".json"

    names = faasr_get_folder_list(prefix=folder)
    map_files = []
    for name in names:
        base = name.rsplit("/", 1)[-1]
        middle = base[len(prefix_part):-len(suffix_part)] if suffix_part else base[len(prefix_part):]
        if base.startswith(prefix_part) and base.endswith(suffix_part) and middle.isdigit():
            map_files.append((int(middle), base))

    if not map_files:
        msg = f"shuffle: no map-result files matching '{input1}' found in folder '{folder}'"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    # Deterministic order of mapper contributions (by mapper rank).
    map_files.sort(key=lambda t: t[0])
    faasr_log(f"shuffle: found {len(map_files)} map outputs: {[b for _, b in map_files]}")

    # Flatten/regroup: gather all partial counts belonging to the same word.
    # Vocabulary M is derived at runtime from the union of words across maps.
    word_to_counts = {}
    for _, base in map_files:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)
        with open(local_in, "r") as f:
            partial = json.load(f)
        if not isinstance(partial, dict):
            raise ValueError(
                f"shuffle: expected {base} to contain a JSON object word->count, "
                f"got {type(partial).__name__}"
            )
        for word, count in partial.items():
            word_to_counts.setdefault(word, []).append(count)
        if os.path.exists(local_in):
            os.remove(local_in)

    # Assign each distinct word a deterministic rank by sorted word order.
    distinct_words = sorted(word_to_counts.keys())
    num_words = len(distinct_words)
    faasr_log(
        f"shuffle: {num_words} distinct words derived at runtime -> "
        f"writing {num_words} ranked shuffled shards: {distinct_words}"
    )

    # Emit one ranked shard per distinct word. Each shard is self-describing:
    # it carries the sorted word set so the reducer can derive its assigned word
    # by rank index, plus this word's partial counts from every mapper.
    for i, word in enumerate(distinct_words, start=1):
        payload = {
            "rank": i,
            "word": word,
            "words": distinct_words,
            "counts": word_to_counts[word],
        }
        local_out = f"shuffled_word_{i}.json"
        with open(local_out, "w") as f:
            json.dump(payload, f)

        remote_out = output1.replace("{rank}", str(i))
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(
            f"shuffle: wrote {remote_out} for word '{word}' with "
            f"counts {word_to_counts[word]}"
        )
        if os.path.exists(local_out):
            os.remove(local_out)
