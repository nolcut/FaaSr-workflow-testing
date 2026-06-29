import os
import json
import string
import tempfile


def map(folder: str, input1: str, output1: str) -> None:
    """
    Reads the assigned text chunk batch_{rank}.txt from S3 (where rank is
    this instance's invocation index), tokenizes the text into words
    (lowercased, stripped of punctuation), counts word frequencies, and
    writes the partial word-count result as map_result_{rank}.json to S3.
    """

    # ── Get rank for this instance ─────────────────────────────────────────
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"map: rank={rank}, max_rank={r['max_rank']}")

    # ── Substitute rank placeholder in filenames ───────────────────────────
    remote_input = input1.format(rank=rank)
    remote_output = output1.format(rank=rank)
    faasr_log(f"map: processing '{remote_input}' → '{remote_output}'")

    # ── Download input batch ───────────────────────────────────────────────
    tmp_dir = tempfile.mkdtemp(prefix="faasr_map_")
    local_input = os.path.join(tmp_dir, f"batch_{rank}.txt")
    local_output = os.path.join(tmp_dir, f"map_result_{rank}.json")

    faasr_log(f"map: downloading '{remote_input}' from folder '{folder}'")
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=remote_input)
    # --- CONTRACT: requires ---
    if "batch_{rank}.txt".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input batch file batch_{rank}.txt must exist in S3 before map can process it")
        raise SystemExit(1)
    if "batch_{rank}.txt".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input batch file batch_{rank}.txt must be non-empty; map raises ValueError on empty input")
        raise SystemExit(1)
    # --- end requires ---

    # ── Read and tokenize text ─────────────────────────────────────────────
    with open(local_input, "r", encoding="utf-8") as fh:
        text = fh.read()

    faasr_log(f"map: read {len(text)} characters from '{remote_input}'")

    if not text.strip():
        msg = f"map: batch file '{remote_input}' is empty — cannot map"
        faasr_log(msg)
        raise ValueError(msg)

    # Tokenize: lowercase and strip all punctuation characters
    translator = str.maketrans("", "", string.punctuation)
    words = text.lower().translate(translator).split()

    faasr_log(f"map: found {len(words)} words after tokenization")

    # ── Count word frequencies ─────────────────────────────────────────────
    word_counts: dict[str, int] = {}
    for word in words:
        if word:
            word_counts[word] = word_counts.get(word, 0) + 1

    faasr_log(f"map: counted {len(word_counts)} unique words")

    # ── Write JSON result ──────────────────────────────────────────────────
    with open(local_output, "w", encoding="utf-8") as fh:
        json.dump(word_counts, fh, ensure_ascii=False)

    # ── Upload result to S3 ────────────────────────────────────────────────
    faasr_put_file(
    # --- CONTRACT: promises ---
    if "map_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: map must upload the word-count result map_result_{rank}.json to S3 after processing")
        raise SystemExit(1)
    if "map_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: map must produce a non-empty JSON word-count file map_result_{rank}.json in S3")
        raise SystemExit(1)
    # --- end promises ---
        local_file=local_output,
        remote_folder=folder,
        remote_file=remote_output,
    )
    faasr_log(f"map: uploaded '{remote_output}' to folder '{folder}'")

    # ── Cleanup ────────────────────────────────────────────────────────────
    os.remove(local_input)
    os.remove(local_output)
    os.rmdir(tmp_dir)

    faasr_log(f"map: rank={rank} complete")