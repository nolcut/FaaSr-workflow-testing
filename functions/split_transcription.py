def split_transcription(folder, input_file, num_maps, output_prefix):
    """
    Stage 2 - Split.

    Download the transcription and partition it into `num_maps` roughly equal
    shards, one per downstream map task. Lines are distributed round-robin so
    that the split works WITHOUT knowing the total word count ahead of time
    (we never need to count words to decide where to cut).

    Shards are written as `<output_prefix>_<rank>.txt` for rank in 1..num_maps
    so that each ranked map invocation can locate its own shard by rank.

    Arguments:
      folder        : S3 folder for the transcription and the shard outputs.
      input_file    : transcription file name (e.g. "transcription.txt").
      num_maps      : number of map shards to produce (e.g. 3).
      output_prefix : prefix for shard files (e.g. "split" -> split_1.txt ...).
    """
    num_maps = int(num_maps)

    faasr_get_file(remote_folder=folder, remote_file=input_file, local_file=input_file)

    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Round-robin lines into num_maps buckets. No global counting required, so
    # this scales to an input whose length/word-count is unknown in advance.
    shards = [[] for _ in range(num_maps)]
    for i, line in enumerate(lines):
        shards[i % num_maps].append(line)

    for r in range(num_maps):
        shard_name = f"{output_prefix}_{r + 1}.txt"
        with open(shard_name, "w", encoding="utf-8") as f:
            f.writelines(shards[r])
        faasr_put_file(local_file=shard_name, remote_folder=folder, remote_file=shard_name)
        faasr_log(
            f"split_transcription: shard {r + 1}/{num_maps} -> "
            f"{folder}/{shard_name} ({len(shards[r])} lines)"
        )
