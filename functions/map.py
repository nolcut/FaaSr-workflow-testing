import json
import os
import string
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "batch_{rank}.txt".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input text batch 'batch_{rank}.txt' must exist in S3 before map can count word frequencies")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "partial_counts_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Partial word counts 'partial_counts_{rank}.json' must exist in S3 after map completes")
        raise SystemExit(1)
# --- end contract helpers ---
def map(folder: str, input1: str, output1: str) -> None:
    """Read this rank's text batch, count word frequencies, upload partial counts JSON."""

    # Determine this instance's rank (1..3)
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    r = faasr_rank()
    rank = r["rank"]

    # Substitute {rank} placeholder in filenames
    remote_input = input1.format(rank=rank)
    remote_output = output1.format(rank=rank)

    faasr_log(f"map rank={rank}: downloading {remote_input} from folder {folder}")

    # Download the text batch assigned to this rank
    local_input = tempfile.mktemp(suffix=".txt")
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=remote_input)

    with open(local_input, "r", encoding="utf-8") as fh:
        text = fh.read()
    os.remove(local_input)

    if not text.strip():
        msg = f"map rank={rank}: input file '{remote_input}' is empty — cannot count words"
        faasr_log(f"ERROR: {msg}")
        raise ValueError(msg)

    # Tokenize: lowercase and strip punctuation from each token
    translator = str.maketrans("", "", string.punctuation)
    tokens = text.split()
    word_counts: dict[str, int] = {}
    for token in tokens:
        word = token.lower().translate(translator)
        if word:  # skip tokens that become empty after stripping punctuation
            word_counts[word] = word_counts.get(word, 0) + 1

    faasr_log(f"map rank={rank}: counted {len(word_counts)} unique words from {len(tokens)} tokens")

    # Write partial counts to a local JSON file and upload to S3
    local_output = tempfile.mktemp(suffix=".json")
    with open(local_output, "w", encoding="utf-8") as fh:
        json.dump(word_counts, fh)

    faasr_log(f"map rank={rank}: uploading {remote_output} to folder {folder}")
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=remote_output)
    os.remove(local_output)

    faasr_log(f"map rank={rank}: complete — wrote partial counts to {remote_output}")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---