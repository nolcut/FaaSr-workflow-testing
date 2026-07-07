import os
import re
import json


def split_transcription(folder: str, input1: str, output1: str) -> None:
    """Read the real transcription text, tokenize into words, and split the
    full word list into N contiguous, roughly-equal ranked JSON shards for the
    downstream parallel map tasks. No synthetic vocabulary is generated.
    """
    # Number of parallel map tasks (fan-out to `map_words`). Kept as a constant
    # so it is generalizable; must match the ranked successor's instance count.
    N = 3

    local_in = "transcription.txt"

    faasr_log(f"split_transcription: downloading '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"split_transcription: input '{input1}' is missing or empty after download"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    with open(local_in, "r", encoding="utf-8") as f:
        text = f.read()

    # Normalize and tokenize: lowercase, extract alphanumeric word tokens.
    # The word count is NOT known ahead of time — handle arbitrary input size.
    words = re.findall(r"[a-z0-9]+", text.lower())

    if not words:
        msg = f"split_transcription: no words found in transcription '{input1}'"
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"split_transcription: tokenized {len(words)} words from '{input1}'")

    # Partition the word list into N contiguous, roughly-equal batches.
    base = len(words) // N
    remainder = len(words) % N
    batches = []
    start = 0
    for i in range(N):
        size = base + (1 if i < remainder else 0)
        batches.append(words[start:start + size])
        start += size

    total_written = 0
    for i in range(1, N + 1):
        batch = batches[i - 1]
        remote_file = output1.replace("{rank}", str(i))
        local_file = f"map_batch_{i}.json"
        with open(local_file, "w", encoding="utf-8") as f:
            json.dump(batch, f)
        faasr_put_file(
            local_file=local_file,
            remote_folder=folder,
            remote_file=remote_file,
        )
        total_written += len(batch)
        faasr_log(
            f"split_transcription: wrote batch {i}/{N} ({len(batch)} words) -> {remote_file}"
        )

    if total_written != len(words):
        msg = (
            f"split_transcription: word count mismatch after partitioning "
            f"({total_written} != {len(words)})"
        )
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_log(
        f"split_transcription: complete, {N} shards written totaling {total_written} words"
    )
