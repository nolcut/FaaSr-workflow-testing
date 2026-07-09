import json
import os


def split(folder: str, input1: str, output1: str) -> None:
    # Read the generated input text: a JSON sequence of word tokens.
    local_in = "input_text.json"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    with open(local_in) as f:
        tokens = json.load(f)

    if not isinstance(tokens, list):
        msg = f"split: expected a JSON list of tokens in '{input1}', got {type(tokens).__name__}"
        faasr_log(msg)
        raise ValueError(msg)

    # Fan-out to ranked successor map_count runs as exactly 3 parallel instances.
    # THIS function is NOT ranked — do not call faasr_rank(); use the literal count.
    n = 3
    total = len(tokens)
    faasr_log(f"split: partitioning {total} tokens into {n} contiguous batches")

    # Contiguous, nearly-equal slices: first (total % n) batches get one extra
    # token so every token is assigned exactly once (generalizable to any length).
    base, extra = divmod(total, n)
    start = 0
    for i in range(1, n + 1):
        size = base + (1 if i <= extra else 0)
        chunk = tokens[start:start + size]
        start += size

        local_out = f"text_batch_{i}.json"
        with open(local_out, "w") as f:
            json.dump(chunk, f)

        remote_out = output1.replace("{rank}", str(i))
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(f"split: wrote batch {i} with {len(chunk)} tokens to '{remote_out}'")

        if os.path.exists(local_out):
            os.remove(local_out)

    if os.path.exists(local_in):
        os.remove(local_in)
