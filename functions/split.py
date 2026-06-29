import json
import os
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "input_text.txt" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input text file 'input_text.txt' must exist in S3 before split can run")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "split_metadata.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Split metadata file 'split_metadata.json' was not found in S3 after split completed")
        raise SystemExit(1)
# --- end contract helpers ---
def split(folder: str, input1: str, output1: str, output2: str) -> None:
    """Read input text, split into 3 word-batches, upload each batch and a metadata JSON."""

    # --- Download input text from S3 ---
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    local_input = tempfile.mktemp(suffix=".txt")
    faasr_log(f"Downloading {input1} from folder {folder}")
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

    with open(local_input, "r", encoding="utf-8") as fh:
        text = fh.read()
    os.remove(local_input)

    words = text.split()
    total_words = len(words)
    faasr_log(f"Input contains {total_words} words")

    if total_words == 0:
        msg = f"Input file '{input1}' is empty or contains no words — cannot split"
        faasr_log(f"ERROR: {msg}")
        raise ValueError(msg)

    # --- Split into exactly 3 batches (fan-out from CONTEXT.md; do NOT call faasr_rank()) ---
    n_batches = 3
    batch_size = (total_words + n_batches - 1) // n_batches  # ceiling division

    batch_filenames = []

    for i in range(1, n_batches + 1):
        start = (i - 1) * batch_size
        end = min(i * batch_size, total_words)
        batch_words = words[start:end]

        batch_remote_file = output1.replace("{rank}", str(i))
        local_batch = tempfile.mktemp(suffix=".txt")

        with open(local_batch, "w", encoding="utf-8") as fh:
            fh.write(" ".join(batch_words))

        faasr_log(f"Uploading batch {i} ({len(batch_words)} words) → {batch_remote_file}")
        faasr_put_file(local_file=local_batch, remote_folder=folder, remote_file=batch_remote_file)
        os.remove(local_batch)

        batch_filenames.append(batch_remote_file)

    # --- Write and upload split metadata ---
    metadata = {
        "n_batches": n_batches,
        "batch_files": batch_filenames,
    }

    local_meta = tempfile.mktemp(suffix=".json")
    with open(local_meta, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh)

    faasr_log(f"Uploading metadata → {output2}")
    faasr_put_file(local_file=local_meta, remote_folder=folder, remote_file=output2)
    os.remove(local_meta)

    faasr_log(f"split complete: {n_batches} batches, metadata written to {output2}")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---