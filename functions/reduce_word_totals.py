import json
import os


def reduce_word_totals(folder: str, input1: str, output1: str) -> None:
    # This function is RANKED (5 parallel reducer instances). Use this instance's
    # own rank to select the single shuffled shard it must reduce.
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"reduce_word_totals: instance rank={rank} of max_rank={r.get('max_rank')}")

    remote_input = input1.replace("{rank}", str(rank))
    local_input = f"shuffled_word_{rank}.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=remote_input)

    with open(local_input, "r") as f:
        data = json.load(f)

    if not isinstance(data, dict) or "words" not in data or "counts" not in data:
        raise ValueError(
            f"reduce_word_totals: {remote_input} is missing expected keys "
            f"('words', 'counts'); got {type(data).__name__}"
        )

    # Derive the rank-to-word mapping deterministically from the sorted set of
    # distinct words present in the shuffled data — no hardcoded vocabulary.
    # This instance's word is the one at its rank index (1-based).
    distinct_words = sorted(data["words"])
    if not (1 <= rank <= len(distinct_words)):
        raise IndexError(
            f"reduce_word_totals: rank {rank} out of range for "
            f"{len(distinct_words)} distinct words"
        )
    assigned_word = distinct_words[rank - 1]

    # Sum all count contributions for the assigned word across all mappers,
    # yielding Zi = total occurrences of that word.
    counts = data["counts"]
    if not isinstance(counts, list):
        raise ValueError(
            f"reduce_word_totals: 'counts' in {remote_input} must be a list, "
            f"got {type(counts).__name__}"
        )
    total = sum(counts)

    faasr_log(
        f"reduce_word_totals: rank={rank} assigned word '{assigned_word}' -> "
        f"total {total} (from contributions {counts})"
    )

    result = {"word": assigned_word, "total": total}
    local_output = f"word_total_{rank}.json"
    with open(local_output, "w") as f:
        json.dump(result, f)

    remote_output = output1.replace("{rank}", str(rank))
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=remote_output)
    faasr_log(f"reduce_word_totals: rank={rank} wrote {remote_output}")

    for p in (local_input, local_output):
        if os.path.exists(p):
            os.remove(p)
