import json
import os


def reduce_count(folder: str, input1: str, output1: str) -> None:
    # This function runs as one of M=5 parallel instances. Determine THIS
    # instance's rank and process only its assigned shuffle group.
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"reduce_count: instance rank {rank} of max_rank {r.get('max_rank')}")

    # Read this reducer's flattened shuffle group (partial counts for one word
    # group across all mappers).
    remote_in = input1.format(rank=rank)
    local_in = f"shuffle_group_{rank}.json"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    with open(local_in) as f:
        group = json.load(f)

    if not isinstance(group, dict):
        msg = f"reduce_count: expected a JSON object in '{remote_in}', got {type(group).__name__}"
        faasr_log(msg)
        raise ValueError(msg)

    # Deterministically derive this reducer's assigned word: take the sorted list
    # of distinct words present in the data and select the entry at position rank
    # (1-indexed -> index rank-1). Generalizable to any vocabulary size.
    words = group.get("words")
    if not isinstance(words, list) or not words:
        msg = f"reduce_count: shuffle group '{remote_in}' missing the sorted distinct-words list"
        faasr_log(msg)
        raise ValueError(msg)
    words = sorted(words)

    if rank - 1 >= len(words):
        msg = (
            f"reduce_count: rank {rank} exceeds the {len(words)} distinct words "
            f"present; no word assigned to this reducer"
        )
        faasr_log(msg)
        raise ValueError(msg)
    word = words[rank - 1]

    # Sum all partial counts for the assigned word across every mapper
    # contribution in the shuffle group.
    partial_counts = group.get("partial_counts", [])
    if not isinstance(partial_counts, list):
        msg = f"reduce_count: 'partial_counts' in '{remote_in}' is not a list"
        faasr_log(msg)
        raise ValueError(msg)
    total = sum(partial_counts)

    faasr_log(
        f"reduce_count: rank {rank} word '{word}' total {total} "
        f"from {len(partial_counts)} partial counts {partial_counts}"
    )

    # Write the final total occurrence count for this reducer's assigned word.
    result = {"word": word, "count": total}
    remote_out = output1.format(rank=rank)
    local_out = f"reduce_result_{rank}.json"
    with open(local_out, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(f"reduce_count: rank {rank} wrote final result to '{remote_out}'")

    for p in (local_in, local_out):
        if os.path.exists(p):
            os.remove(p)
