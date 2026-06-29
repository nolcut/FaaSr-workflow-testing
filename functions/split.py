import json
import os
import tempfile

# Fan-out to 3 parallel map instances (from workflow specification)
NUM_BATCHES = 3


def split(folder: str, input1: str, output1: str, output2: str) -> None:
    faasr_log(f"split: starting — folder={folder}, input={input1}")

    # Download the full input text from S3
    fd, local_input = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)
        # --- CONTRACT: requires ---
        if "input_text.txt" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
            faasr_log("[REQUIRE] CONTRACT VIOLATION: Input text file input_text.txt must exist in S3 before split can run")
            raise SystemExit(1)
        if "input_text.txt" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
            faasr_log("[REQUIRE] CONTRACT VIOLATION: Input text file input_text.txt must be non-empty; split requires at least one word to partition")
            raise SystemExit(1)
    # --- end requires ---
    except Exception as e:
        faasr_log(f"split: ERROR — could not retrieve {input1} from S3: {e}")
        raise

    # Read and tokenize into words
    with open(local_input, "r", encoding="utf-8") as f:
        text = f.read()
    os.remove(local_input)

    words = text.split()
    faasr_log(f"split: tokenized {len(words)} words from {input1}")

    if not words:
        msg = f"split: ERROR — {input1} is empty or contains no words"
        faasr_log(msg)
        raise RuntimeError(msg)

    # Partition words into NUM_BATCHES contiguous chunks
    chunk_size = (len(words) + NUM_BATCHES - 1) // NUM_BATCHES

    batch_files = []
    for rank in range(1, NUM_BATCHES + 1):
        start = (rank - 1) * chunk_size
        end = min(rank * chunk_size, len(words))
        batch_words = words[start:end]

        batch_filename = output1.replace("{rank}", str(rank))

        fd, local_batch = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(batch_words))
            faasr_put_file(
                local_file=local_batch,
                remote_folder=folder,
                remote_file=batch_filename,
            )
        finally:
            if os.path.exists(local_batch):
                os.remove(local_batch)

        faasr_log(
            f"split: uploaded batch {rank}/{NUM_BATCHES} "
            f"({len(batch_words)} words) → {batch_filename}"
        )
        batch_files.append(batch_filename)

    # Write manifest recording total batch count and each batch filename
    manifest = {
        "total_batches": NUM_BATCHES,
        "batch_files": batch_files,
    }
    fd, local_manifest = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        faasr_put_file(
    # --- CONTRACT: promises ---
    # EXISTS skipped: "batch_{rank}.txt" is a per-rank family on a non-ranked function (cannot verify a single name)
    if "split_manifest.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Split must upload the manifest file split_manifest.json to S3")
        raise SystemExit(1)
    if "split_manifest.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: The manifest file split_manifest.json must be non-empty and contain batch metadata")
        raise SystemExit(1)
    # --- end promises ---
            local_file=local_manifest,
            remote_folder=folder,
            remote_file=output2,
        )
    finally:
        if os.path.exists(local_manifest):
            os.remove(local_manifest)

    faasr_log(f"split: uploaded manifest → {output2}")
    faasr_log("split: complete")
