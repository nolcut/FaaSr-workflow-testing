def generate_input(folder, output_file, words, total_words, seed):
    """
    Dataset generation for the MapReduce benchmark (dataset-specific).

    Produces an input corpus of `total_words` (W) tokens drawn from the
    vocabulary `words`, with each word appearing an equal number of times
    (W / len(words)) and the whole sequence shuffled randomly.

    For the benchmark: words = ["cat","dog","bird","horse","pig"],
    total_words = 5000  ->  M = 5 distinct words, 1000 occurrences each.

    Output: a single whitespace-separated text file written to
    `<folder>/<output_file>` in the default S3 datastore.
    """
    import random

    n_words = len(words)
    if n_words == 0:
        raise ValueError("`words` must contain at least one word")

    # Even distribution: each distinct word gets the same number of copies.
    per_word = total_words // n_words
    remainder = total_words - per_word * n_words

    tokens = []
    for w in words:
        tokens.extend([w] * per_word)
    # Distribute any remainder (when W is not divisible by M) over the first words
    for i in range(remainder):
        tokens.append(words[i % n_words])

    # Shuffle randomly (seeded for reproducibility of the benchmark)
    rng = random.Random(seed)
    rng.shuffle(tokens)

    local_file = output_file
    with open(local_file, "w") as f:
        f.write(" ".join(tokens))

    faasr_put_file(local_folder=".", local_file=local_file,
                   remote_folder=folder, remote_file=output_file)

    faasr_log(
        f"generate_input: wrote {len(tokens)} tokens "
        f"({n_words} distinct words, {per_word} each) to {folder}/{output_file}"
    )
