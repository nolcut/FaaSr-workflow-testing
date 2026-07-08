"""
MapReduce - SPLIT stage.

Generates the synthetic input text (W words drawn evenly from a fixed
vocabulary, then shuffled at random) and partitions it into `num_maps`
batches. Each batch is written to S3 as `<chunk_prefix>_<i>.txt` so that
the N parallel map actions can each pick up their own chunk by rank.

The generator is the only stage that "knows" the vocabulary; the map and
reduce stages are fully generic word-count operations.
"""

import os
import random


def split_input(folder="mapreduce",
                num_maps=3,
                total_words=5000,
                vocabulary=None,
                chunk_prefix="chunk",
                seed=None):
    if vocabulary is None:
        vocabulary = ["cat", "dog", "bird", "horse", "pig"]

    num_maps = int(num_maps)
    total_words = int(total_words)

    if seed is not None:
        random.seed(int(seed))

    # ---- Generate W words, distributed as evenly as possible across the vocab
    vocab_size = len(vocabulary)
    base = total_words // vocab_size          # equal share per word
    remainder = total_words % vocab_size      # spread leftover words

    words = []
    for i, word in enumerate(vocabulary):
        count = base + (1 if i < remainder else 0)
        words.extend([word] * count)

    # ---- Shuffle randomly so the words are not grouped
    random.shuffle(words)

    faasr_log(
        f"[split] Generated {len(words)} words from vocabulary "
        f"{vocabulary} (M={vocab_size} distinct words)."
    )

    # ---- Partition into num_maps contiguous, near-equal chunks
    n = len(words)
    chunk_base = n // num_maps
    chunk_rem = n % num_maps

    start = 0
    for rank in range(1, num_maps + 1):
        size = chunk_base + (1 if (rank - 1) < chunk_rem else 0)
        chunk = words[start:start + size]
        start += size

        local_file = f"{chunk_prefix}_{rank}.txt"
        with open(local_file, "w") as f:
            f.write(" ".join(chunk))

        faasr_put_file(
            local_folder=".",
            local_file=local_file,
            remote_folder=folder,
            remote_file=local_file,
        )
        faasr_log(f"[split] Wrote chunk {rank}/{num_maps} "
                  f"({len(chunk)} words) -> {folder}/{local_file}")

    faasr_log(f"[split] Done. Fanning out to {num_maps} map actions.")
