import os
import re
import json

# Number of downstream ranked `map_step` instances (fan-out). Each gets one shard.
NUM_SHARDS = 4


def split_transcription(folder: str, input1: str, output1: str) -> None:
    """Read the transcription text, tokenize into words, and partition the full
    word list into NUM_SHARDS contiguous, roughly equal batches. Write each batch
    as one ranked JSON file (a list of words) for the parallel map tasks to consume.

    folder  : remote S3 folder
    input1  : remote transcription filename (e.g. 'transcription.txt')
    output1 : ranked output template (e.g. 'map_batch_{rank}.json')
    """
    local_in = "transcription.txt"

    faasr_log(f"split_transcription: fetching transcription '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"split_transcription: input transcription '{input1}' is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    with open(local_in, "r", encoding="utf-8") as f:
        text = f.read()

    # Normalize/tokenize: lowercase, strip punctuation, split on whitespace.
    lowered = text.lower()
    words = re.findall(r"[a-z0-9]+", lowered)

    if not words:
        msg = f"split_transcription: no words could be tokenized from '{input1}'"
        faasr_log(msg)
        raise ValueError(msg)

    total = len(words)
    faasr_log(f"split_transcription: tokenized {total} words; partitioning into {NUM_SHARDS} shards")

    # Partition into NUM_SHARDS contiguous, roughly equal-sized batches.
    base = total // NUM_SHARDS
    remainder = total % NUM_SHARDS

    start = 0
    for i in range(1, NUM_SHARDS + 1):
        # Distribute the remainder across the first `remainder` shards.
        size = base + (1 if (i - 1) < remainder else 0)
        batch = words[start:start + size]
        start += size

        local_out = f"map_batch_{i}.json"
        with open(local_out, "w", encoding="utf-8") as f:
            json.dump(batch, f)

        remote_out = output1.format(rank=i)
        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(f"split_transcription: wrote shard {i}/{NUM_SHARDS} with {len(batch)} words -> '{remote_out}'")

    faasr_log("split_transcription: partitioning complete")
