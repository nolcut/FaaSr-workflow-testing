import json
import os
from collections import Counter


def map(folder: str, input1: str, output1: str) -> None:
    # This function is RANKED: each of the parallel instances handles only its
    # own shard, identified by its own rank (1..N).
    r = faasr_rank()
    rank = r["rank"]

    remote_input = input1.format(rank=rank)
    local_input = f"chunk_{rank}.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=remote_input)

    with open(local_input, "r") as f:
        words = json.load(f)

    if not isinstance(words, list):
        raise ValueError(
            f"Expected a JSON array of words in {remote_input}, got {type(words).__name__}"
        )

    faasr_log(f"[map rank {rank}] read {len(words)} words from {folder}/{remote_input}")

    # Count occurrences of each distinct word present in this shard. Vocabulary
    # is derived purely from the data — never hardcoded.
    counts = dict(Counter(words))

    faasr_log(f"[map rank {rank}] counted {len(counts)} distinct words: {counts}")

    remote_output = output1.format(rank=rank)
    local_output = f"partial_counts_{rank}.json"
    with open(local_output, "w") as f:
        json.dump(counts, f)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=remote_output)
    faasr_log(f"[map rank {rank}] wrote partial counts to {folder}/{remote_output}")

    for p in (local_input, local_output):
        try:
            os.remove(p)
        except OSError:
            pass
