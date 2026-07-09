"""
MapReduce - SPLIT stage (dataset generation + partitioning).

This is the ONLY workflow-specific / benchmark-specific function: it fabricates
the input text for the benchmark. Everything downstream (map/shuffle/reduce/
collect) is fully generalizable.

Benchmark parameters (supplied via the workflow JSON Arguments):
  * words        : the M distinct words used to build the corpus
  * total_words  : W, the total number of words in the corpus
  * num_maps     : N, the number of map partitions (= number of chunk files)

The corpus is built so that every word appears (as close as possible to)
evenly, then shuffled uniformly at random.  The shuffled corpus is partitioned
into N contiguous batches, one chunk file per map rank.

FaaSr runtime helpers (faasr_get_file, faasr_put_file, faasr_log, ...) are
injected into the global namespace by the FaaSr platform at execution time.
"""

import os
import random


def generate_and_split(chunks_folder="MapReduce/chunks",
                       dataset_folder="MapReduce/input",
                       dataset_file="dataset.txt",
                       chunk_prefix="chunk",
                       num_maps=3,
                       total_words=5000,
                       words=None,
                       seed=None):

    if words is None:
        words = ["cat", "dog", "bird", "horse", "pig"]

    num_maps = int(num_maps)
    total_words = int(total_words)
    M = len(words)

    faasr_log(
        f"[split] Generating corpus: W={total_words} words, "
        f"M={M} distinct words {words}, N={num_maps} map partitions."
    )

    # ---- Build an evenly distributed multiset of words -------------------
    base = total_words // M          # words per distinct token (floor)
    remainder = total_words % M      # spread the leftover one-by-one
    corpus = []
    for i, w in enumerate(words):
        count = base + (1 if i < remainder else 0)
        corpus.extend([w] * count)

    # ---- Shuffle uniformly at random ------------------------------------
    if seed is not None:
        random.seed(int(seed))
    random.shuffle(corpus)

    # ---- Persist the full dataset (whitespace separated) ----------------
    local_dataset = dataset_file
    with open(local_dataset, "w") as fh:
        fh.write(" ".join(corpus))
    faasr_put_file(local_folder=".", local_file=local_dataset,
                   remote_folder=dataset_folder, remote_file=dataset_file)

    # ---- Partition into N as-even-as-possible contiguous batches --------
    n = len(corpus)
    per = n // num_maps
    rem = n % num_maps

    start = 0
    for r in range(1, num_maps + 1):
        # ranks [1..rem] receive one extra element so no word is dropped
        size = per + (1 if r <= rem else 0)
        chunk = corpus[start:start + size]
        start += size

        chunk_name = f"{chunk_prefix}_{r}.txt"
        with open(chunk_name, "w") as fh:
            fh.write(" ".join(chunk))
        faasr_put_file(local_folder=".", local_file=chunk_name,
                       remote_folder=chunks_folder, remote_file=chunk_name)
        faasr_log(f"[split] Wrote {chunks_folder}/{chunk_name} "
                  f"({len(chunk)} words).")

    faasr_log(
        f"[split] Done. {num_maps} chunks written to '{chunks_folder}'. "
        f"Fanning out to {num_maps} parallel map ranks."
    )
