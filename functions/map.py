import collections
import json
import os
import re
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "batch_{rank}.txt".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input batch file 'batch_{rank}.txt' must exist in S3 before the map function can process it")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "map_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Partial word-count JSON 'map_result_{rank}.json' must have been uploaded to S3 after the map function completes")
        raise SystemExit(1)
# --- end contract helpers ---
def map(folder: str, input1: str, output1: str) -> None:
    """
    Reads the assigned text batch for this rank, tokenizes the words
    (lowercased, punctuation stripped), counts each word's frequency,
    and uploads the partial word-count as a JSON file.

    Parameters
    ----------
    folder  : S3 folder (remote_folder) for all I/O
    input1  : remote filename template for the input batch, e.g. "batch_{rank}.txt"
    output1 : remote filename template for the output map result, e.g. "map_result_{rank}.json"
    """

    # ------------------------------------------------------------------ #
    # 1. Determine this instance's rank                                    #
    # ------------------------------------------------------------------ #
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"map: starting rank {rank} of {r['max_rank']}")

    # Resolve rank-specific filenames
    remote_input = input1.format(rank=rank)
    remote_output = output1.format(rank=rank)

    # ------------------------------------------------------------------ #
    # 2. Download the batch file                                           #
    # ------------------------------------------------------------------ #
    with tempfile.NamedTemporaryFile(
        mode="r", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp_in:
        local_input = tmp_in.name

    try:
        faasr_get_file(
            local_file=local_input,
            remote_folder=folder,
            remote_file=remote_input,
        )

        if not os.path.exists(local_input) or os.path.getsize(local_input) == 0:
            msg = f"map: batch file '{remote_input}' is missing or empty in folder '{folder}'"
            faasr_log(msg)
            raise RuntimeError(msg)

        with open(local_input, "r", encoding="utf-8") as fh:
            raw_text = fh.read()

        faasr_log(f"map: downloaded '{remote_input}' ({len(raw_text)} bytes)")

    finally:
        if os.path.exists(local_input):
            os.remove(local_input)

    # ------------------------------------------------------------------ #
    # 3. Tokenize: split on whitespace, lowercase, strip punctuation       #
    # ------------------------------------------------------------------ #
    # Strip leading/trailing punctuation from each token; keep internal
    # apostrophes (e.g. contractions) and hyphens intact within words.
    word_counts: collections.Counter = collections.Counter()

    for token in raw_text.split():
        # Remove all leading and trailing non-alphanumeric characters
        word = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", token).lower()
        if word:
            word_counts[word] += 1

    faasr_log(
        f"map: rank {rank} counted {sum(word_counts.values())} token(s), "
        f"{len(word_counts)} unique word(s)"
    )

    # ------------------------------------------------------------------ #
    # 4. Write and upload the partial word-count JSON                      #
    # ------------------------------------------------------------------ #
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp_out:
        local_output = tmp_out.name
        json.dump(dict(word_counts), tmp_out, indent=2)

    try:
        faasr_put_file(
            local_file=local_output,
            remote_folder=folder,
            remote_file=remote_output,
        )
        faasr_log(f"map: uploaded partial word-count → '{remote_output}'")
    finally:
        if os.path.exists(local_output):
            os.remove(local_output)

    faasr_log(f"map: rank {rank} done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---