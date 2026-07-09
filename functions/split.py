import json
import os


def split(folder: str, input1: str, output1: str) -> None:
    # Number of parallel map instances (ranked successor map_word_count runs x3).
    # Hardcoded here; THIS function is not ranked. Trivially generalizable by
    # changing N — the partitioning logic below works for any chunk count.
    N = 3

    local_input = "raw_input_text.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

    with open(local_input, "r") as f:
        words = json.load(f)

    if not isinstance(words, list):
        raise ValueError(
            f"split: expected {input1} to contain a JSON array of words, "
            f"got {type(words).__name__}"
        )

    total = len(words)
    faasr_log(f"split: read {total} words from {input1}; partitioning into N={N} chunks")

    # Contiguous partitioning into N roughly equal batches. Sizes differ by at
    # most 1 (the first `remainder` chunks get one extra word). Every input word
    # is placed in exactly one chunk — no loss, no duplication.
    base = total // N
    remainder = total % N

    start = 0
    emitted = 0
    for i in range(1, N + 1):
        size = base + (1 if i <= remainder else 0)
        chunk = words[start:start + size]
        start += size
        emitted += len(chunk)

        local_chunk = f"text_chunk_{i}.json"
        with open(local_chunk, "w") as f:
            json.dump(chunk, f)

        remote_chunk = output1.replace("{rank}", str(i))
        faasr_put_file(local_file=local_chunk, remote_folder=folder, remote_file=remote_chunk)
        faasr_log(f"split: wrote {remote_chunk} with {len(chunk)} words")

        if os.path.exists(local_chunk):
            os.remove(local_chunk)

    if emitted != total:
        raise ValueError(
            f"split: partition covered {emitted} words but input had {total} — "
            f"word loss/duplication detected"
        )

    faasr_log(f"split: partitioned all {total} words across {N} chunks with no loss")

    if os.path.exists(local_input):
        os.remove(local_input)
