import os
import json


def split(folder: str, input1: str, output1: str) -> None:
    # Number of map tasks (N). This function feeds the ranked successor
    # map_word_count, which runs as exactly N=3 parallel instances, so we
    # must emit exactly 3 shards. This function is NOT itself ranked, so we
    # do NOT call faasr_rank(); the count is the literal fan-out value.
    num_batches = 3

    local_in = "input_text.json"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    with open(local_in, "r") as f:
        content = f.read()

    if not content.strip():
        faasr_log(f"split: input file {folder}/{input1} is empty or missing.")
        raise ValueError(f"Input file {input1} is empty")

    words = json.loads(content)
    if not isinstance(words, list):
        faasr_log(
            f"split: expected a JSON array of word tokens in {input1}, "
            f"got {type(words).__name__}."
        )
        raise ValueError("Input is not a JSON array of word tokens")

    total = len(words)
    faasr_log(
        f"split: read {total} word tokens; partitioning into {num_batches} "
        f"batches (order preserved, remainder distributed evenly)."
    )

    # Distribute remainder as evenly as possible across the leading batches:
    # the first (total % num_batches) batches get one extra word.
    base = total // num_batches
    remainder = total % num_batches

    start = 0
    for i in range(1, num_batches + 1):
        size = base + (1 if i <= remainder else 0)
        batch = words[start:start + size]
        start += size

        local_out = f"split_batch_{i}.json"
        with open(local_out, "w") as f:
            json.dump(batch, f)

        remote_out = output1.replace("{rank}", str(i))
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(f"split: wrote batch {i} with {len(batch)} words to {folder}/{remote_out}.")

        if os.path.exists(local_out):
            os.remove(local_out)

    if start != total:
        faasr_log(f"split: distributed {start} words but expected {total}.")
        raise ValueError("Word count mismatch after partitioning")

    if os.path.exists(local_in):
        os.remove(local_in)
