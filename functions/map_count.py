import json
import os
from collections import Counter


def map_count(folder: str, input1: str, output1: str) -> None:
    # This function runs as one of N=3 parallel instances. Determine THIS
    # instance's rank and process only its assigned shard.
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"map_count: instance rank {rank} of max_rank {r.get('max_rank')}")

    # Read this instance's assigned text chunk (a JSON list of word tokens).
    remote_in = input1.format(rank=rank)
    local_in = f"text_batch_{rank}.json"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    with open(local_in) as f:
        tokens = json.load(f)

    if not isinstance(tokens, list):
        msg = f"map_count: expected a JSON list of tokens in '{remote_in}', got {type(tokens).__name__}"
        faasr_log(msg)
        raise ValueError(msg)

    # Count word occurrences within this chunk. Fully generalizable: the
    # vocabulary is derived from the tokens themselves, not hardcoded.
    counts = dict(Counter(tokens))
    faasr_log(
        f"map_count: rank {rank} counted {len(tokens)} tokens into "
        f"{len(counts)} distinct words"
    )

    # Write the partial word->count mapping keyed by this mapper's rank.
    remote_out = output1.format(rank=rank)
    local_out = f"map_result_{rank}.json"
    with open(local_out, "w") as f:
        json.dump(counts, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(f"map_count: rank {rank} wrote partial counts to '{remote_out}'")

    for p in (local_in, local_out):
        if os.path.exists(p):
            os.remove(p)
