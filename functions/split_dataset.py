def split_dataset(folder="MapReduce", input_file="words.txt", n_splits=4,
                  splits_folder="MapReduce/splits"):
    """Split the extracted word list into ``n_splits`` roughly equal shards so that
    each concurrent mapper (identified by its rank) can process one shard.

    Reads:  {folder}/{input_file}
    Writes: {splits_folder}/part_1.txt ... part_{n_splits}.txt
    """
    n_splits = int(n_splits)

    # Download the full word list
    faasr_get_file(
        remote_folder=folder,
        remote_file=input_file,
        local_folder=".",
        local_file="words.txt",
    )

    with open("words.txt", "r", encoding="utf-8") as fh:
        words = [w for w in fh.read().splitlines() if w.strip()]

    # Round-robin assignment gives balanced shards regardless of ordering
    shards = [[] for _ in range(n_splits)]
    for idx, word in enumerate(words):
        shards[idx % n_splits].append(word)

    # Write and upload one shard per mapper rank (ranks are 1-indexed)
    for i in range(n_splits):
        local_name = f"part_{i + 1}.txt"
        with open(local_name, "w", encoding="utf-8") as fh:
            fh.write("\n".join(shards[i]))
        faasr_put_file(
            local_folder=".",
            local_file=local_name,
            remote_folder=splits_folder,
            remote_file=local_name,
        )

    faasr_log(
        f"split_dataset: split {len(words)} words into {n_splits} shards "
        f"under {splits_folder}/"
    )
