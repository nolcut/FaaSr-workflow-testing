import os
import json
from collections import Counter


def map_word_count(folder: str, input1: str, output1: str) -> None:
    # This function is RANKED: it runs as N parallel instances. Use this
    # instance's own rank to process ONLY its assigned batch shard.
    r = faasr_rank()
    rank = r["rank"]

    remote_in = input1.format(rank=rank)
    local_in = f"split_batch_{rank}.json"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    with open(local_in, "r") as f:
        content = f.read()

    if not content.strip():
        faasr_log(f"map_word_count[{rank}]: input {folder}/{remote_in} is empty or missing.")
        raise ValueError(f"Input batch {remote_in} is empty")

    words = json.loads(content)
    if not isinstance(words, list):
        faasr_log(
            f"map_word_count[{rank}]: expected a JSON array of word tokens in "
            f"{remote_in}, got {type(words).__name__}."
        )
        raise ValueError("Input batch is not a JSON array of word tokens")

    # Count each distinct word in this chunk. Generalizable to any vocabulary:
    # we count whatever words appear, with no hardcoded word list.
    counts = dict(Counter(words))
    faasr_log(
        f"map_word_count[{rank}]: counted {len(words)} tokens into "
        f"{len(counts)} distinct words."
    )

    remote_out = output1.format(rank=rank)
    local_out = f"map_counts_{rank}.json"
    with open(local_out, "w") as f:
        json.dump(counts, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(f"map_word_count[{rank}]: wrote partial counts to {folder}/{remote_out}.")

    for p in (local_in, local_out):
        if os.path.exists(p):
            os.remove(p)
