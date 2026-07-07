import json
import os
import random


def split(folder: str, output1: str) -> None:
    # Benchmark parameters (fixed by spec).
    W = 5000                                   # total number of words
    N = 3                                      # number of downstream map instances (shards)
    WORDS = ["cat", "dog", "bird", "horse", "pig"]  # M = 5 distinct words
    M = len(WORDS)
    SEED = 42                                  # fixed seed for reproducibility

    faasr_log(
        f"split: generating {W} words from {M} distinct words {WORDS}, "
        f"distributed evenly and shuffled, then partitioned into {N} batches."
    )

    if W % M != 0:
        raise ValueError(f"W={W} is not evenly divisible by M={M}")

    # Build the word list: each distinct word appears W/M times (1000 each).
    per_word = W // M
    text = []
    for w in WORDS:
        text.extend([w] * per_word)

    # Shuffle randomly with a fixed seed for reproducibility.
    rng = random.Random(SEED)
    rng.shuffle(text)

    if len(text) != W:
        raise ValueError(f"Generated {len(text)} words, expected {W}")

    # Partition the shuffled sequence into N batches (as even as possible).
    batches = [text[i::N] for i in range(N)]

    total = sum(len(b) for b in batches)
    if total != W:
        raise ValueError(f"Partition covers {total} words, expected {W}")

    # Write each batch to its own ranked JSON output file (batch_{rank}.json).
    for i in range(1, N + 1):
        batch = batches[i - 1]
        local_file = f"batch_{i}.json"
        with open(local_file, "w") as f:
            json.dump(batch, f)
        remote_file = output1.replace("{rank}", str(i))
        faasr_put_file(
            local_file=local_file,
            remote_folder=folder,
            remote_file=remote_file,
        )
        faasr_log(f"split: wrote {len(batch)} words to {remote_file}")
        os.remove(local_file)

    faasr_log("split: complete")
