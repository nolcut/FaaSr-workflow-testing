import os
import json
import random


def split(folder: str, output1: str) -> None:
    # MapReduce word-count benchmark parameters (generalizable via constants).
    VOCABULARY = ["cat", "dog", "bird", "horse", "pig"]  # M = 5 distinct words
    W = 5000          # total number of words in the generated input text
    N = 3             # number of parallel map tasks (fan-out to `map`)

    M = len(VOCABULARY)
    if W % M != 0:
        faasr_log(
            f"split: total word count W={W} is not evenly divisible by "
            f"vocabulary size M={M}; cannot distribute words evenly."
        )
        raise ValueError(f"W ({W}) must be divisible by M ({M})")

    per_word = W // M  # each word appears W/M times (1000)
    faasr_log(
        f"split: generating input text of W={W} words from vocabulary "
        f"{VOCABULARY} (each word x{per_word})"
    )

    # Build the full word list: each word distributed evenly, then shuffled.
    words = []
    for w in VOCABULARY:
        words.extend([w] * per_word)
    random.shuffle(words)
    faasr_log(f"split: built and shuffled word list of length {len(words)}")

    # Partition the shuffled word list into N contiguous, roughly equal batches.
    base = len(words) // N
    remainder = len(words) % N
    batches = []
    start = 0
    for i in range(N):
        size = base + (1 if i < remainder else 0)
        batches.append(words[start:start + size])
        start += size

    total_written = 0
    for i in range(1, N + 1):
        batch = batches[i - 1]
        remote_file = output1.replace("{rank}", str(i))
        local_file = f"map_batch_{i}.json"
        with open(local_file, "w") as f:
            json.dump(batch, f)
        faasr_put_file(
            local_file=local_file,
            remote_folder=folder,
            remote_file=remote_file,
        )
        total_written += len(batch)
        faasr_log(
            f"split: wrote batch {i}/{N} ({len(batch)} words) -> {remote_file}"
        )

    if total_written != len(words):
        faasr_log(
            f"split: word count mismatch after partitioning "
            f"({total_written} != {len(words)})"
        )
        raise RuntimeError("split: partitioning lost or duplicated words")

    faasr_log(f"split: complete, {N} shards written totaling {total_written} words")
