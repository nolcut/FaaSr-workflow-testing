import os
import json
from collections import Counter


def map_step(folder: str, input1: str, output1: str) -> None:
    # Determine this instance's shard from its parallel rank.
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"map_step: starting instance rank={rank} (max_rank={r.get('max_rank')})")

    remote_in = input1.format(rank=rank)
    remote_out = output1.format(rank=rank)

    local_in = f"map_batch_{rank}.json"
    local_out = f"map_counts_{rank}.json"

    # Fetch this instance's assigned transcription word-list shard.
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"map_step: input shard '{remote_in}' is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    with open(local_in, "r", encoding="utf-8") as f:
        words = json.load(f)

    if not isinstance(words, list):
        msg = f"map_step: input shard '{remote_in}' is not a JSON list of words (got {type(words).__name__})"
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"map_step: rank {rank} read {len(words)} words from {remote_in}")

    # Count occurrences of each word within this chunk. Fully generalizable to
    # any vocabulary discovered from the real transcribed text (no hardcoded words).
    counts = Counter(str(w) for w in words)
    result = dict(counts)

    faasr_log(
        f"map_step: rank {rank} produced per-chunk counts for {len(result)} distinct words "
        f"totaling {sum(result.values())} words"
    )

    with open(local_out, "w", encoding="utf-8") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(f"map_step: rank {rank} wrote per-chunk word counts -> {remote_out}")
