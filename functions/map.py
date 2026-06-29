import json
import os
import string
import tempfile
from collections import Counter


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "batch_{rank}.txt".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input batch file 'batch_{rank}.txt' must exist in S3 before the map function can process it")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "map_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Map result file 'map_result_{rank}.json' should have been uploaded to S3 after word count processing")
        raise SystemExit(1)
# --- end contract helpers ---
def map(folder: str, input1: str, output1: str) -> None:
    """
    Reads the assigned text chunk from S3 for this mapper's batch index
    (determined via faasr_rank()), tokenizes the text into words (lowercased,
    stripped of punctuation), counts the frequency of each word, and writes
    the intermediate word count results as a JSON file to S3 for the shuffle step.
    """
    # ── 1. Determine this instance's rank ────────────────────────────────────
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"map: starting rank={rank} max_rank={r['max_rank']}")

    # Substitute {rank} in filenames
    remote_input = input1.format(rank=rank)
    remote_output = output1.format(rank=rank)

    # ── 2. Download this rank's batch file ───────────────────────────────────
    local_input = tempfile.mktemp(suffix=".txt")
    faasr_log(f"Downloading batch file '{remote_input}' from folder '{folder}'")
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=remote_input)

    with open(local_input, "r", encoding="utf-8") as fh:
        text = fh.read()
    os.unlink(local_input)

    if not text.strip():
        msg = f"Batch file '{remote_input}' is empty — cannot map"
        faasr_log(msg)
        raise ValueError(msg)

    # ── 3. Tokenize: lowercase + strip punctuation ───────────────────────────
    # The split function writes words one per line (joined with "\n"), but those
    # words may still carry leading/trailing punctuation from the original text.
    translator = str.maketrans("", "", string.punctuation)
    counts: Counter = Counter()
    for token in text.split():
        word = token.lower().translate(translator)
        if word:  # skip empty strings left after stripping punctuation
            counts[word] += 1

    total_words = sum(counts.values())
    faasr_log(f"Rank {rank}: counted {total_words} tokens across {len(counts)} unique words")

    # ── 4. Write word counts to a local JSON file ────────────────────────────
    local_output = tempfile.mktemp(suffix=".json")
    with open(local_output, "w", encoding="utf-8") as fh:
        json.dump(counts, fh, indent=2, sort_keys=True)

    # ── 5. Upload JSON result to S3 ───────────────────────────────────────────
    faasr_log(f"Uploading map result '{remote_output}' to folder '{folder}'")
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=remote_output)
    os.unlink(local_output)

    faasr_log(f"map rank={rank} complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---