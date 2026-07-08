import random


def split(folder, N=3, W=5000, vocab=None, seed=42):
    """
    MapReduce SPLIT stage.

    Generates the input text (W words drawn evenly from `vocab` and shuffled
    randomly) and partitions it into N batches, one per map worker.

    Each chunk is written to S3 at:
        {folder}/{invocation_id}/input/chunk_{r}.txt   (r = 1 .. N)

    Args are provided by the workflow JSON "Arguments" block:
        folder : base S3 prefix for this workflow's artifacts
        N      : number of map workers / chunks
        W      : total number of words to generate
        vocab  : list of vocabulary words (default: cat/dog/bird/horse/pig)
        seed   : RNG seed so the run is reproducible
    """
    if vocab is None:
        vocab = ["cat", "dog", "bird", "horse", "pig"]
    N = int(N)
    W = int(W)
    seed = int(seed)

    inv = faasr_invocation_id()
    base = f"{folder}/{inv}"

    # --- Build an evenly-distributed multiset of W words over the vocabulary ---
    V = len(vocab)
    per_word = [W // V] * V
    for i in range(W % V):          # spread any remainder across the first words
        per_word[i] += 1

    words = []
    for w, c in zip(vocab, per_word):
        words.extend([w] * c)

    # --- Shuffle randomly (seeded for reproducibility) ---
    rng = random.Random(seed)
    rng.shuffle(words)

    # --- Partition into N chunks as evenly as possible ---
    chunk_sizes = [W // N] * N
    for i in range(W % N):
        chunk_sizes[i] += 1

    idx = 0
    for r in range(1, N + 1):
        size = chunk_sizes[r - 1]
        chunk = words[idx:idx + size]
        idx += size

        local_file = f"chunk_{r}.txt"
        with open(local_file, "w") as f:
            f.write(" ".join(chunk))

        faasr_put_file(
            local_file=local_file,
            remote_folder=f"{base}/input",
            remote_file=f"chunk_{r}.txt",
        )

    faasr_log(
        f"split: generated W={W} words from {V}-word vocab, "
        f"partitioned into N={N} chunks under {base}/input"
    )
