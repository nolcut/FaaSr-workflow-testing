import json
import os
from collections import Counter


def map_word_count(folder: str, input1: str, output1: str) -> None:
    # This function is RANKED (3 parallel instances). Use this instance's own
    # rank to select the single text chunk it must process.
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"map_word_count: instance rank={rank} of max_rank={r.get('max_rank')}")

    remote_input = input1.replace("{rank}", str(rank))
    local_input = f"text_chunk_{rank}.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=remote_input)

    with open(local_input, "r") as f:
        words = json.load(f)

    if not isinstance(words, list):
        raise ValueError(
            f"map_word_count: expected {remote_input} to contain a JSON array of "
            f"words, got {type(words).__name__}"
        )

    # Count how often each distinct word occurs in this chunk. No hardcoded
    # vocabulary — count whatever words appear (generalizable to any vocabulary).
    counts = Counter(words)
    partial = dict(counts)

    faasr_log(
        f"map_word_count: rank={rank} counted {len(words)} words into "
        f"{len(partial)} distinct words"
    )

    remote_output = output1.replace("{rank}", str(rank))
    local_output = f"map_result_{rank}.json"
    with open(local_output, "w") as f:
        json.dump(partial, f)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=remote_output)
    faasr_log(f"map_word_count: rank={rank} wrote {remote_output}")

    for p in (local_input, local_output):
        if os.path.exists(p):
            os.remove(p)
