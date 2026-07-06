import json
import os


def map(folder: str, input1: str, output1: str) -> None:
    # Determine this instance's shard from its rank (1..N).
    r = faasr_rank()
    rank = r["rank"]

    remote_in = input1.format(rank=rank)
    remote_out = output1.format(rank=rank)

    local_in = f"text_chunk_{rank}.json"
    local_out = f"map_partial_counts_{rank}.json"

    faasr_log(f"map: rank={rank} reading chunk {remote_in}")

    # Fetch this instance's assigned text chunk.
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    with open(local_in, "r") as f:
        words = json.load(f)

    if not isinstance(words, list):
        raise ValueError(
            f"map: expected a JSON list of words in {remote_in}, got {type(words).__name__}"
        )

    # Count how often each word occurs within this chunk (Yi).
    counts = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1

    faasr_log(
        f"map: rank={rank} counted {len(words)} words into "
        f"{len(counts)} distinct entries: {counts}"
    )

    with open(local_out, "w") as f:
        json.dump(counts, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(f"map: rank={rank} wrote partial counts {remote_out}")

    for p in (local_in, local_out):
        if os.path.exists(p):
            os.remove(p)
