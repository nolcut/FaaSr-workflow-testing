"""FaaSr MapReduce benchmark - dataset generation.

This is the ONLY dataset-specific (non-generalizable) function in the
workflow.  It synthesizes the benchmark input text: W words drawn from a
fixed vocabulary, each vocabulary word appearing an equal number of times,
and the whole sequence shuffled into random order.

Benchmark parameters (set via the workflow JSON Arguments):
    W = num_words           (total number of words, e.g. 5000)
    M = len(words)          (number of distinct words, e.g. 5 -> reducers)
"""

import random


def generate_dataset(folder, output_file, num_words, words, seed=None):
    """Generate the benchmark input text and upload it to S3.

    Args:
        folder:      remote S3 folder for all MapReduce artifacts.
        output_file: remote filename for the generated input text.
        num_words:   total number of words to emit (W).
        words:       vocabulary list, e.g. ["cat","dog","bird","horse","pig"].
        seed:        optional RNG seed for reproducible shuffling.
    """
    num_words = int(num_words)
    vocab = list(words)
    m = len(vocab)
    if m == 0:
        raise ValueError("words vocabulary must be non-empty")

    # Distribute W words as evenly as possible across the M vocabulary words.
    base = num_words // m
    remainder = num_words % m
    tokens = []
    for i, w in enumerate(vocab):
        count = base + (1 if i < remainder else 0)
        tokens.extend([w] * count)

    # Shuffle randomly so the words are not grouped by type.
    rng = random.Random(seed)
    rng.shuffle(tokens)

    # Write one word per line (whitespace-delimited text).
    local_file = "input.txt"
    with open(local_file, "w") as f:
        f.write("\n".join(tokens))
        f.write("\n")

    faasr_put_file(
        local_file=local_file,
        remote_folder=folder,
        remote_file=output_file,
    )

    faasr_log(
        f"generate_dataset: wrote {len(tokens)} words "
        f"({m} distinct: {vocab}) to {folder}/{output_file}"
    )
