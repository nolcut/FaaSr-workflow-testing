"""FaaSr MapReduce benchmark - split (partition) stage.

Generalizable: reads an arbitrary whitespace-delimited input text from S3
and partitions its tokens into N nearly-equal contiguous batches, one per
downstream map action.  It does NOT know anything about the vocabulary.

InvokeNext: map(N)  -- fans out to N ranked map invocations.
"""


def split_text(folder, input_file, num_mappers, chunk_prefix):
    """Partition the input text into num_mappers chunks.

    Args:
        folder:       remote S3 folder for all MapReduce artifacts.
        input_file:   remote filename of the input text to partition.
        num_mappers:  number of batches / map actions (N).
        chunk_prefix: prefix for per-chunk output files; chunk i (1-based)
                      is written as "<chunk_prefix>_<i>.txt".
    """
    n = int(num_mappers)
    if n < 1:
        raise ValueError("num_mappers must be >= 1")

    faasr_get_file(
        local_file="input.txt",
        remote_folder=folder,
        remote_file=input_file,
    )

    with open("input.txt") as f:
        tokens = f.read().split()

    total = len(tokens)

    # Contiguous, nearly-equal partitioning: the first `remainder` chunks get
    # one extra token so every token lands in exactly one chunk.
    base = total // n
    remainder = total % n

    start = 0
    for i in range(1, n + 1):
        size = base + (1 if i <= remainder else 0)
        chunk = tokens[start:start + size]
        start += size

        local_chunk = f"chunk_{i}.txt"
        with open(local_chunk, "w") as f:
            f.write("\n".join(chunk))
            if chunk:
                f.write("\n")

        remote_chunk = f"{chunk_prefix}_{i}.txt"
        faasr_put_file(
            local_file=local_chunk,
            remote_folder=folder,
            remote_file=remote_chunk,
        )
        faasr_log(
            f"split_text: chunk {i}/{n} -> {folder}/{remote_chunk} "
            f"({len(chunk)} words)"
        )

    faasr_log(f"split_text: partitioned {total} words into {n} chunks")
