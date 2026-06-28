import json
import os
import re
import tempfile


def map(folder: str, input1: str, output1: str) -> None:
    """
    Mapper: reads the text chunk for this rank, counts word frequencies,
    and writes a partial word-count JSON to S3.

    Parameters
    ----------
    folder  : S3 folder (prefix) used for all FaaSr I/O.
    input1  : Template for the per-chunk remote filename (e.g. "chunk_{rank}.txt").
    output1 : Template for the partial-count remote filename
              (e.g. "partial_counts_{rank}.json").
    """
    # ------------------------------------------------------------------ #
    # 1. Determine this instance's rank                                    #
    # ------------------------------------------------------------------ #
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"map[{rank}]: starting (max_rank={r['max_rank']})")

    # Substitute {rank} in the filename templates
    chunk_remote = input1.format(rank=rank)
    counts_remote = output1.format(rank=rank)

    # ------------------------------------------------------------------ #
    # 2. Download the assigned text chunk from S3                          #
    # ------------------------------------------------------------------ #
    local_chunk = tempfile.mktemp(suffix=".txt")
    faasr_log(f"map[{rank}]: downloading {folder}/{chunk_remote}")
    faasr_get_file(local_file=local_chunk, remote_folder=folder, remote_file=chunk_remote)
    # --- CONTRACT: requires ---
    if not os.path.exists("chunk_{rank}.txt"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input text chunk for this rank must exist in S3 before mapping")
        raise SystemExit(1)
    if not os.path.exists("chunk_{rank}.txt") or os.path.getsize("chunk_{rank}.txt") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input text chunk for this rank must not be empty — an empty chunk produces no word counts")
        raise SystemExit(1)
    # --- end requires ---

    if not os.path.exists(local_chunk) or os.path.getsize(local_chunk) == 0:
        msg = f"map[{rank}]: chunk file '{chunk_remote}' is missing or empty in S3 folder '{folder}'"
        faasr_log(msg)
        raise ValueError(msg)

    # ------------------------------------------------------------------ #
    # 3. Read text and tokenise into normalised words                      #
    # Normalisation: lowercase + strip leading/trailing non-alphanumeric. #
    # ------------------------------------------------------------------ #
    with open(local_chunk, "r", encoding="utf-8") as fh:
        text = fh.read()
    os.remove(local_chunk)

    raw_tokens = text.split()
    faasr_log(f"map[{rank}]: tokenising {len(raw_tokens)} raw tokens")

    word_counts: dict = {}
    for token in raw_tokens:
        # Lowercase and strip non-alphanumeric characters from both ends
        word = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", token.lower())
        if word:  # skip tokens that reduced to empty string
            word_counts[word] = word_counts.get(word, 0) + 1

    faasr_log(
        f"map[{rank}]: counted {sum(word_counts.values())} words "
        f"({len(word_counts)} unique)"
    )

    # ------------------------------------------------------------------ #
    # 4. Write partial counts as JSON and upload to S3                     #
    # ------------------------------------------------------------------ #
    local_counts = tempfile.mktemp(suffix=".json")
    with open(local_counts, "w", encoding="utf-8") as fh:
        json.dump(word_counts, fh, indent=2, sort_keys=True)

    faasr_log(f"map[{rank}]: uploading partial counts to {folder}/{counts_remote}")
    # --- CONTRACT: promises ---
    if not os.path.exists("partial_counts_{rank}.json"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Partial word-count JSON must exist in S3 after the map step completes")
        raise SystemExit(1)
    if not os.path.exists("partial_counts_{rank}.json") or os.path.getsize("partial_counts_{rank}.json") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Partial word-count JSON must not be empty after upload")
        raise SystemExit(1)
    try:
        import json as _json; _json.loads(open("partial_counts_{rank}.json").read())
    except Exception as _e:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Partial word-count output must be valid JSON (a string-to-integer mapping): " + str(_e))
        raise SystemExit(1)
    # --- end promises ---
    faasr_put_file(
        local_file=local_counts,
        remote_folder=folder,
        remote_file=counts_remote,
    )
    os.remove(local_counts)

    faasr_log(f"map[{rank}]: complete")