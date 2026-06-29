import json
import os
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "input_text.txt" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input text file 'input_text.txt' must exist in S3 folder 'workflow_data2' before split can run")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "manifest.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Manifest file 'manifest.json' was not uploaded to S3 after split completed")
        raise SystemExit(1)
# --- end contract helpers ---
def split(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Reads the full input text from S3 folder 'workflow_data2', tokenises it into
    words, partitions the words into 2 approximately equal batches for parallel map
    processing, uploads each batch as a separate file, and writes a manifest JSON
    describing the batches for the downstream shuffle step.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    num_batches = 2  # hard-coded: map runs as 2 parallel instances

    # ── 1. Download input text ────────────────────────────────────────────────
    local_input = tempfile.mktemp(suffix=".txt")
    faasr_log(f"Downloading input file '{input1}' from folder 'workflow_data2'")
    faasr_get_file(local_file=local_input, remote_folder="workflow_data2", remote_file=input1)

    with open(local_input, "r", encoding="utf-8") as fh:
        text = fh.read()
    os.unlink(local_input)

    words = text.split()
    total_words = len(words)
    faasr_log(f"Total words tokenised: {total_words}")

    if total_words == 0:
        msg = "Input file is empty or contains no words — cannot split"
        faasr_log(msg)
        raise ValueError(msg)

    # ── 2. Partition words into batches and upload ────────────────────────────
    batch_files = []
    for i in range(1, num_batches + 1):
        start = (i - 1) * total_words // num_batches
        end = i * total_words // num_batches
        batch_words = words[start:end]

        local_batch = tempfile.mktemp(suffix=".txt")
        with open(local_batch, "w", encoding="utf-8") as fh:
            fh.write("\n".join(batch_words))

        remote_batch = output1.replace("{rank}", str(i))
        faasr_log(
            f"Uploading batch {i}/{num_batches}: '{remote_batch}' ({len(batch_words)} words)"
        )
        faasr_put_file(
            local_file=local_batch, remote_folder=folder, remote_file=remote_batch
        )
        os.unlink(local_batch)
        batch_files.append(remote_batch)

    # ── 3. Write and upload manifest ──────────────────────────────────────────
    manifest = {
        "num_batches": num_batches,
        "batch_files": batch_files,
    }
    local_manifest = tempfile.mktemp(suffix=".json")
    with open(local_manifest, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    faasr_log(f"Uploading manifest '{output2}'")
    faasr_put_file(
        local_file=local_manifest, remote_folder=folder, remote_file=output2
    )
    os.unlink(local_manifest)

    faasr_log("split complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---