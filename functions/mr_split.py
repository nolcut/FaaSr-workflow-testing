def mr_split(folder, input_file, n_splits, batch_prefix):
    """
    SPLIT phase (fully generalizable).

    Partitions an arbitrary whitespace-delimited input text into `n_splits`
    (= N) roughly equal batches and writes one file per batch:
        <folder>/<batch_prefix><i>.txt   for i in 1..N

    The number of batches must match the fan-out declared in this action's
    InvokeNext (e.g. "map(N)") so that map rank r reads batch r.

    Does not assume anything about the vocabulary or contents of the text.
    """
    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file=input_file)

    with open(input_file) as f:
        tokens = f.read().split()

    n = int(n_splits)
    if n < 1:
        raise ValueError("n_splits must be >= 1")

    total = len(tokens)
    # Balanced contiguous partition: first `remainder` batches get one extra token.
    base = total // n
    remainder = total % n

    start = 0
    for i in range(1, n + 1):
        size = base + (1 if i <= remainder else 0)
        chunk = tokens[start:start + size]
        start += size

        batch_name = f"{batch_prefix}{i}.txt"
        with open(batch_name, "w") as f:
            f.write(" ".join(chunk))

        faasr_put_file(local_folder=".", local_file=batch_name,
                       remote_folder=folder, remote_file=batch_name)
        faasr_log(f"mr_split: batch {i}/{n} -> {folder}/{batch_name} ({len(chunk)} tokens)")

    faasr_log(f"mr_split: partitioned {total} tokens into {n} batches")
