import json
import os


def map_phase(folder: str, input1: str, output1: str) -> None:
    # Fixed vocabulary (M = 5 distinct words) for the word-count benchmark.
    # Shared with the upstream read_pdf producer and the downstream
    # shuffle/reduce catalog stages.
    WORDS = ["cat", "dog", "bird", "horse", "pig"]

    # This ranked instance's own index (1..N).
    r = faasr_rank()
    rank = r["rank"]

    in_name = input1.replace("{rank}", str(rank))
    out_name = output1.replace("{rank}", str(rank))

    faasr_log(f"map_phase[rank={rank}]: reading input partition {in_name}")

    local_in = f"text_chunk_{rank}.json"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=in_name)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = (
            f"map_phase[rank={rank}]: input partition '{in_name}' is missing "
            f"or empty after fetch"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    with open(local_in, "r") as f:
        tokens = json.load(f)

    if not isinstance(tokens, list):
        raise ValueError(
            f"map_phase[rank={rank}]: expected a JSON list of words in "
            f"{in_name}, got {type(tokens).__name__}"
        )

    # Count how often each vocabulary word occurs in this chunk.
    counts = {w: 0 for w in WORDS}
    for tok in tokens:
        if tok in counts:
            counts[tok] += 1
        else:
            raise ValueError(
                f"map_phase[rank={rank}]: encountered token '{tok}' not in the "
                f"fixed vocabulary {WORDS}"
            )

    faasr_log(f"map_phase[rank={rank}]: counted {len(tokens)} tokens -> {counts}")

    local_out = f"partial_counts_{rank}.json"
    with open(local_out, "w") as f:
        json.dump(counts, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=out_name)
    faasr_log(f"map_phase[rank={rank}]: wrote partial counts to {out_name}")

    for p in (local_in, local_out):
        if os.path.exists(p):
            os.remove(p)

    faasr_log(f"map_phase[rank={rank}]: complete")
