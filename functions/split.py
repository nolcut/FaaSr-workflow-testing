import json
import os
import random

from FaaSr_py.client.py_client_stubs import (
    faasr_invocation_id,
    faasr_log,
    faasr_put_file,
)


def split(
    folder="mapreduce",
    num_maps=3,
    total_words=5000,
    vocabulary=None,
    seed=42,
):
    """
    MapReduce SPLIT stage.

    Generates the input text (``total_words`` words drawn from ``vocabulary``,
    each word distributed evenly and then shuffled randomly) and partitions it
    into ``num_maps`` (=N) roughly equal text chunks, one per downstream map
    invocation. Chunk i is written to ``<folder>/<invocation_id>/chunks/chunk_i.txt``.

    Although the default vocabulary is the fixed 5-word set, this stage is
    generalizable to any vocabulary / N / W passed via the workflow Arguments.
    """
    if vocabulary is None:
        vocabulary = ["cat", "dog", "bird", "horse", "pig"]

    num_maps = int(num_maps)
    total_words = int(total_words)
    seed = int(seed)
    vocab = list(vocabulary)

    base_path = f"{folder}/{faasr_invocation_id()}"

    # --- Build the input text: even distribution across the vocabulary --------
    words = []
    per_word = total_words // len(vocab)
    remainder = total_words % len(vocab)
    for i, w in enumerate(vocab):
        count = per_word + (1 if i < remainder else 0)
        words.extend([w] * count)

    # --- Shuffle randomly (deterministic via seed for reproducibility) --------
    rng = random.Random(seed)
    rng.shuffle(words)

    faasr_log(
        f"split: generated {len(words)} words from vocabulary {vocab} "
        f"(target W={total_words}, N={num_maps})"
    )

    # --- Partition into N roughly equal contiguous chunks ---------------------
    chunk_base = len(words) // num_maps
    chunk_rem = len(words) % num_maps
    idx = 0
    for rank in range(1, num_maps + 1):
        size = chunk_base + (1 if rank <= chunk_rem else 0)
        chunk_words = words[idx:idx + size]
        idx += size

        local_file = f"chunk_{rank}.txt"
        with open(local_file, "w") as f:
            f.write(" ".join(chunk_words))
        faasr_put_file(
            local_file=local_file,
            remote_folder=f"{base_path}/chunks",
            remote_file=f"chunk_{rank}.txt",
        )
        faasr_log(f"split: wrote chunk {rank}/{num_maps} with {len(chunk_words)} words")

    # --- Persist a small manifest describing this run ------------------------
    manifest = {
        "num_maps": num_maps,
        "total_words": len(words),
        "vocabulary": vocab,
        "seed": seed,
    }
    with open("split_manifest.json", "w") as f:
        json.dump(manifest, f)
    faasr_put_file(
        local_file="split_manifest.json",
        remote_folder=base_path,
        remote_file="split_manifest.json",
    )
    faasr_log(f"split: complete; {num_maps} chunks ready under {base_path}/chunks")
