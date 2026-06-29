import os
import tempfile


def split(folder: str, input1: str, output1: str) -> None:
    """
    Reads the full input text file from S3, splits it into N equal (or
    near-equal) batches by word count, and writes each batch as a separate
    text file back to S3.  N is taken from faasr_rank()["max_rank"], which
    the FaaSr payload sets to the fan-out width of the downstream `map` step.
    Output files are named by replacing '{rank}' in output1 with 1 … N.
    """

    # ── Determine number of batches from FaaSr payload ────────────────────
    rank_info = faasr_rank()
    n_batches = rank_info["max_rank"]
    faasr_log(f"split: will produce {n_batches} batch(es) from '{input1}'")

    if n_batches < 1:
        msg = f"split: max_rank={n_batches} is invalid (must be >= 1)"
        faasr_log(msg)
        raise ValueError(msg)

    # ── Download input file ────────────────────────────────────────────────
    tmp_dir = tempfile.mkdtemp(prefix="faasr_split_")
    local_input = os.path.join(tmp_dir, "input.txt")

    faasr_log(f"split: downloading '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)
    # --- CONTRACT: requires ---
    if "input_text.txt" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'input_text.txt' must exist in S3 before splitting")
        raise SystemExit(1)
    if "input_text.txt" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input file 'input_text.txt' must be non-empty — splitting an empty file is not allowed")
        raise SystemExit(1)
    # --- end requires ---

    # ── Read and tokenise ──────────────────────────────────────────────────
    with open(local_input, "r", encoding="utf-8") as fh:
        text = fh.read()

    words = text.split()
    total_words = len(words)
    faasr_log(f"split: total words = {total_words}")

    if total_words == 0:
        msg = "split: input file contains no words — cannot split"
        faasr_log(msg)
        raise ValueError(msg)

    # ── Partition words into N near-equal batches ──────────────────────────
    # The first (total_words % n_batches) batches get one extra word.
    base_size = total_words // n_batches
    remainder = total_words % n_batches

    batches = []
    start = 0
    for i in range(n_batches):
        batch_size = base_size + (1 if i < remainder else 0)
        batches.append(words[start : start + batch_size])
        start += batch_size

    # ── Write each batch to S3 ─────────────────────────────────────────────
    for rank in range(1, n_batches + 1):
        batch_words = batches[rank - 1]
        local_batch = os.path.join(tmp_dir, f"batch_{rank}.txt")

        with open(local_batch, "w", encoding="utf-8") as fh:
            fh.write(" ".join(batch_words))

        remote_file = output1.replace("{rank}", str(rank))
        faasr_put_file(
    # --- CONTRACT: promises ---
    # EXISTS skipped: "batch_{rank}.txt" is a per-rank family on a non-ranked function (cannot verify a single name)
    # --- end promises ---
            local_file=local_batch,
            remote_folder=folder,
            remote_file=remote_file,
        )
        faasr_log(
            f"split: uploaded batch {rank}/{n_batches} "
            f"({len(batch_words)} words) → '{remote_file}'"
        )

        os.remove(local_batch)

    # ── Cleanup ────────────────────────────────────────────────────────────
    os.remove(local_input)
    os.rmdir(tmp_dir)

    faasr_log("split: complete")