import json
import os
import tempfile


def split(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Splits a plain-text corpus into N batches (fan-out to 3 ranked `map` instances).

    Parameters
    ----------
    folder  : S3 folder (prefix) used for all FaaSr I/O.
    input1  : Remote filename of the corpus (e.g. "corpus.txt").
    output1 : Template for per-chunk remote filenames (e.g. "chunk_{rank}.txt").
    output2 : Remote filename for the metadata JSON (e.g. "split_metadata.json").
    """
    # Number of batches equals the fan-out to the ranked `map` successor (x3).
    N_BATCHES = 3

    # ------------------------------------------------------------------ #
    # 1. Download corpus from S3                                           #
    # ------------------------------------------------------------------ #
    local_corpus = tempfile.mktemp(suffix=".txt")
    faasr_log(f"split: downloading corpus from {folder}/{input1}")
    faasr_get_file(local_file=local_corpus, remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    if not os.path.exists("corpus.txt"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input corpus file must exist in S3 before splitting")
        raise SystemExit(1)
    if not os.path.exists("corpus.txt") or os.path.getsize("corpus.txt") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input corpus file must not be empty — cannot split zero words")
        raise SystemExit(1)
    # --- end requires ---

    if not os.path.exists(local_corpus) or os.path.getsize(local_corpus) == 0:
        msg = f"split: corpus file '{input1}' is missing or empty in S3 folder '{folder}'"
        faasr_log(msg)
        raise ValueError(msg)

    # ------------------------------------------------------------------ #
    # 2. Read corpus and tokenise into words                               #
    # ------------------------------------------------------------------ #
    with open(local_corpus, "r", encoding="utf-8") as fh:
        text = fh.read()
    os.remove(local_corpus)

    words = text.split()
    total_words = len(words)
    faasr_log(f"split: corpus has {total_words} words; splitting into {N_BATCHES} batches")

    if total_words == 0:
        msg = "split: corpus is empty — cannot split"
        faasr_log(msg)
        raise ValueError(msg)

    # ------------------------------------------------------------------ #
    # 3. Partition words into N_BATCHES roughly equal chunks               #
    # Distribute any remainder across the first batches (+/-1 word).      #
    # ------------------------------------------------------------------ #
    base_size = total_words // N_BATCHES
    remainder = total_words % N_BATCHES

    chunks = []
    start = 0
    for i in range(N_BATCHES):
        size = base_size + (1 if i < remainder else 0)
        chunks.append(words[start : start + size])
        start += size

    # ------------------------------------------------------------------ #
    # 4. Write each chunk to a local temp file and upload to S3            #
    # ------------------------------------------------------------------ #
    metadata = {
        "n_batches": N_BATCHES,
        "chunks": [],
    }

    for rank, chunk_words in enumerate(chunks, start=1):
        chunk_filename = output1.replace("{rank}", str(rank))
        local_chunk = tempfile.mktemp(suffix=".txt")
        with open(local_chunk, "w", encoding="utf-8") as fh:
            fh.write(" ".join(chunk_words))
        faasr_log(
            f"split: uploading {chunk_filename} "
            f"(batch {rank}/{N_BATCHES}, {len(chunk_words)} words)"
        )
    # --- CONTRACT: promises ---
    if not os.path.exists("chunk_1.txt"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Chunk file for rank 1 must exist in S3 after splitting")
        raise SystemExit(1)
    if not os.path.exists("chunk_2.txt"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Chunk file for rank 2 must exist in S3 after splitting")
        raise SystemExit(1)
    if not os.path.exists("chunk_3.txt"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Chunk file for rank 3 must exist in S3 after splitting")
        raise SystemExit(1)
    if not os.path.exists("chunk_1.txt") or os.path.getsize("chunk_1.txt") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Chunk file for rank 1 must contain at least one word")
        raise SystemExit(1)
    if not os.path.exists("chunk_2.txt") or os.path.getsize("chunk_2.txt") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Chunk file for rank 2 must contain at least one word")
        raise SystemExit(1)
    if not os.path.exists("chunk_3.txt") or os.path.getsize("chunk_3.txt") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Chunk file for rank 3 must contain at least one word")
        raise SystemExit(1)
    if not os.path.exists("split_metadata.json"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Metadata JSON file must exist in S3 after splitting")
        raise SystemExit(1)
    if not os.path.exists("split_metadata.json") or os.path.getsize("split_metadata.json") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Metadata JSON file must not be empty after splitting")
        raise SystemExit(1)
    try:
        import json as _json; _json.loads(open("split_metadata.json").read())
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Metadata output must be valid JSON: " + str(_e))
        raise SystemExit(1)
    # INPUTS_UNCHANGED: corpus.txt (tracked at require time)
    # --- end promises ---
        faasr_put_file(
            local_file=local_chunk,
            remote_folder=folder,
            remote_file=chunk_filename,
        )
        os.remove(local_chunk)
        metadata["chunks"].append(
            {"filename": chunk_filename, "word_count": len(chunk_words)}
        )

    # ------------------------------------------------------------------ #
    # 5. Write and upload metadata JSON                                    #
    # ------------------------------------------------------------------ #
    local_meta = tempfile.mktemp(suffix=".json")
    with open(local_meta, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)
    faasr_log(f"split: uploading metadata to {folder}/{output2}")
    faasr_put_file(
        local_file=local_meta,
        remote_folder=folder,
        remote_file=output2,
    )
    os.remove(local_meta)

    faasr_log("split: complete")