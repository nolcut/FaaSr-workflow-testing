import json
import os
import random


def split(folder: str, output1: str) -> None:
    # MapReduce word-count benchmark parameters.
    W = 5000                                     # total number of words
    N = 3                                         # number of map functions (fan-out)
    vocabulary = ["cat", "dog", "bird", "horse", "pig"]
    M = len(vocabulary)                           # number of distinct words (5)

    faasr_log(
        f"split: generating input text of W={W} words over M={M} vocabulary "
        f"{vocabulary}, partitioning into N={N} batches"
    )

    if W % M != 0:
        raise ValueError(f"W={W} is not evenly divisible by M={M}")

    # Generate the input text: each word distributed evenly, then shuffled.
    per_word = W // M                             # 1000 occurrences of each word
    words = []
    for w in vocabulary:
        words.extend([w] * per_word)

    # Shuffle randomly to interleave the words.
    random.shuffle(words)

    if len(words) != W:
        raise ValueError(f"generated {len(words)} words, expected {W}")

    # Partition the shuffled word list into N batches of roughly equal size.
    base = len(words) // N
    remainder = len(words) % N
    batches = []
    start = 0
    for i in range(N):
        size = base + (1 if i < remainder else 0)
        batches.append(words[start:start + size])
        start += size

    total_written = sum(len(b) for b in batches)
    if total_written != W:
        raise ValueError(f"partitioned {total_written} words, expected {W}")

    # Write each batch as a separate ranked output file (one per map instance).
    for i in range(1, N + 1):
        batch = batches[i - 1]
        remote_file = output1.replace("{rank}", str(i))
        local_file = f"text_chunk_{i}.json"
        with open(local_file, "w") as f:
            json.dump(batch, f)
        faasr_put_file(
            local_file=local_file,
            remote_folder=folder,
            remote_file=remote_file,
        )
        faasr_log(f"split: wrote {remote_file} with {len(batch)} words")
        if os.path.exists(local_file):
            os.remove(local_file)

    faasr_log(f"split: completed, wrote {N} chunks totaling {W} words")
