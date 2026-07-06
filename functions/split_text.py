import json
import os


def split_text(folder: str, input1: str, output1: str) -> None:
    """Split the OCR-extracted word list into ranked chunks for the map stage.

    Reads the OCR text produced by the upstream ``ocr_pdf`` step (``input1``, a
    JSON array of words), tokenizes it into a flat word list, partitions that
    list into N=3 batches of roughly equal size, and writes each batch as a
    ranked JSON output file (``output1`` with ``{rank}`` substituted) consumed
    by the parallel map functions.
    """
    # Fan-out to the ranked `map` successor is exactly 3 parallel instances.
    N = 3

    local_in = "ocr_text.json"

    faasr_log(f"split_text: fetching OCR text '{input1}' from folder '{folder}'")

    # Fetch the OCR-extracted text JSON from S3.
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"split_text: OCR text input '{input1}' in folder '{folder}' is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    with open(local_in, "r") as f:
        data = json.load(f)

    # The upstream OCR step writes a JSON array of words. Accept either that
    # array directly, or a single string that still needs whitespace tokenizing.
    if isinstance(data, list):
        words = [str(w) for w in data]
    elif isinstance(data, str):
        words = data.split()
    else:
        msg = (
            f"split_text: expected a JSON list of words (or a string) in "
            f"'{input1}', got {type(data).__name__}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    if not words:
        msg = f"split_text: OCR text input '{input1}' contained no words"
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(
        f"split_text: read {len(words)} words; partitioning into N={N} batches"
    )

    # Partition the word list into N batches of roughly equal size.
    base = len(words) // N
    remainder = len(words) % N
    batches = []
    start = 0
    for i in range(N):
        size = base + (1 if i < remainder else 0)
        batches.append(words[start:start + size])
        start += size

    total_written = sum(len(b) for b in batches)
    if total_written != len(words):
        msg = f"split_text: partitioned {total_written} words, expected {len(words)}"
        faasr_log(msg)
        raise ValueError(msg)

    # Write each batch as a separate ranked output file (one per map instance).
    for i in range(1, N + 1):
        batch = batches[i - 1]
        remote_file = output1.replace("{rank}", str(i))
        local_file = f"text_chunk_{i}.json"
        with open(local_file, "w") as f:
            json.dump(batch, f)
        faasr_put_file(
            local_file=local_file,
            remote_folder=folder,
            remote_file=remote_file,
        )
        faasr_log(f"split_text: wrote {remote_file} with {len(batch)} words")
        if os.path.exists(local_file):
            os.remove(local_file)

    if os.path.exists(local_in):
        os.remove(local_in)

    faasr_log(
        f"split_text: completed, wrote {N} chunks totaling {len(words)} words"
    )
