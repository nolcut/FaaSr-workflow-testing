def split_dataset(folder="MapReduce", input_file="words.txt", num_parts=3):
    """
    Stage 2 of the MapReduce pipeline.

    Downloads the extracted word list, splits it into `num_parts` roughly-equal
    shards and uploads each shard to `folder`/splits/part_<rank>.txt. The number
    of shards MUST match the rank count used to fan out `map_words` in the
    workflow JSON (map_words(N)), so each map invocation with rank R reads
    part_R.txt.
    """
    num_parts = int(num_parts)

    # 1. Download the full word list produced by extract_words.
    faasr_log(f"split_dataset: downloading {folder}/{input_file}")
    faasr_get_file(
        remote_folder=folder,
        remote_file=input_file,
        local_folder=".",
        local_file="words.txt",
    )

    with open("words.txt") as fh:
        words = fh.read().split()

    total = len(words)
    faasr_log(f"split_dataset: splitting {total} words into {num_parts} parts")

    # 2. Compute contiguous, balanced chunk boundaries.
    #    Ranks are 1-indexed in FaaSr, so part files are named part_1..part_N.
    base = total // num_parts
    remainder = total % num_parts

    start = 0
    for i in range(num_parts):
        rank = i + 1
        size = base + (1 if i < remainder else 0)
        chunk = words[start:start + size]
        start += size

        local_name = f"part_{rank}.txt"
        with open(local_name, "w") as fh:
            fh.write(" ".join(chunk))

        faasr_put_file(
            local_folder=".",
            local_file=local_name,
            remote_folder=f"{folder}/splits",
            remote_file=f"part_{rank}.txt",
        )
        faasr_log(
            f"split_dataset: wrote {len(chunk)} words to "
            f"{folder}/splits/part_{rank}.txt"
        )
