import json
import os


def split(folder: str, input1: str, output1: str) -> None:
    # Number of parallel mapper instances (ranked successor `map` runs x3).
    # THIS function is not ranked, so the count is the literal fan-out from the
    # spec, NOT derived from faasr_rank().
    num_batches = 3

    local_input = "input_text.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

    with open(local_input, "r") as f:
        words = json.load(f)

    if not isinstance(words, list):
        raise ValueError(
            f"Expected a JSON array of words in {input1}, got {type(words).__name__}"
        )

    total = len(words)
    faasr_log(f"Read {total} words from {folder}/{input1}; partitioning into {num_batches} batches")

    # Partition contiguously into roughly equal batches, distributing the
    # remainder across the earliest batches so no words are dropped/duplicated.
    base = total // num_batches
    remainder = total % num_batches

    start = 0
    for i in range(1, num_batches + 1):
        size = base + (1 if i <= remainder else 0)
        chunk = words[start:start + size]
        start += size

        local_chunk = f"chunk_{i}.json"
        with open(local_chunk, "w") as f:
            json.dump(chunk, f)

        remote_chunk = output1.replace("{rank}", str(i))
        faasr_put_file(local_file=local_chunk, remote_folder=folder, remote_file=remote_chunk)
        faasr_log(f"Wrote batch {i}/{num_batches} with {len(chunk)} words to {folder}/{remote_chunk}")

        try:
            os.remove(local_chunk)
        except OSError:
            pass

    if start != total:
        raise RuntimeError(
            f"Partitioning error: assigned {start} words but input had {total}"
        )

    try:
        os.remove(local_input)
    except OSError:
        pass
