import json
import os
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "corpus.txt" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input corpus file 'corpus.txt' must exist in S3 before split can run")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "split_metadata.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Split must upload the metadata JSON describing batch count and filenames to S3")
        raise SystemExit(1)
# --- end contract helpers ---
def split(folder: str, input1: str, output1: str, output2: str) -> None:
    """
    Reads the full corpus from S3, splits its words into N even batches (one per
    parallel map worker), uploads each batch file, and uploads a JSON metadata file
    that records N and the list of batch filenames.

    Parameters
    ----------
    folder  : S3 folder (remote_folder) for all I/O
    input1  : remote filename of the corpus (e.g. "corpus.txt")
    output1 : remote filename template for batch files (e.g. "batch_{rank}.txt")
    output2 : remote filename for the metadata JSON (e.g. "split_metadata.json")
    """

    # ------------------------------------------------------------------ #
    # 1. Determine N — the number of parallel map workers                  #
    # ------------------------------------------------------------------ #
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    rank_info = faasr_rank()
    n_batches = rank_info.get("max_rank", 1)
    faasr_log(f"split: will create {n_batches} batch(es) from '{input1}'")

    # ------------------------------------------------------------------ #
    # 2. Download the corpus                                               #
    # ------------------------------------------------------------------ #
    with tempfile.NamedTemporaryFile(
        mode="r", suffix=".txt", delete=False
    ) as tmp_in:
        local_corpus = tmp_in.name

    try:
        faasr_get_file(
            local_file=local_corpus,
            remote_folder=folder,
            remote_file=input1,
        )

        if not os.path.exists(local_corpus) or os.path.getsize(local_corpus) == 0:
            msg = f"split: corpus file '{input1}' is missing or empty in folder '{folder}'"
            faasr_log(msg)
            raise RuntimeError(msg)

        with open(local_corpus, "r", encoding="utf-8") as fh:
            words = fh.read().split()

        faasr_log(f"split: corpus contains {len(words)} word(s)")

        if not words:
            msg = f"split: corpus file '{input1}' contains no words"
            faasr_log(msg)
            raise RuntimeError(msg)

        # ------------------------------------------------------------------ #
        # 3. Partition words into n_batches chunks as evenly as possible       #
        # ------------------------------------------------------------------ #
        total = len(words)
        # distribute remainder words across the first `remainder` batches
        base_size, remainder = divmod(total, n_batches)

        batch_filenames = []
        offset = 0

        for rank in range(1, n_batches + 1):
            chunk_size = base_size + (1 if rank <= remainder else 0)
            chunk = words[offset: offset + chunk_size]
            offset += chunk_size

            # Resolve the output filename template for this rank
            batch_remote = output1.replace("{rank}", str(rank))
            batch_filenames.append(batch_remote)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as tmp_batch:
                local_batch = tmp_batch.name
                tmp_batch.write("\n".join(chunk))

            try:
                faasr_put_file(
                    local_file=local_batch,
                    remote_folder=folder,
                    remote_file=batch_remote,
                )
                faasr_log(
                    f"split: uploaded batch {rank}/{n_batches} "
                    f"({chunk_size} word(s)) → '{batch_remote}'"
                )
            finally:
                if os.path.exists(local_batch):
                    os.remove(local_batch)

        # ------------------------------------------------------------------ #
        # 4. Write and upload the metadata JSON                                #
        # ------------------------------------------------------------------ #
        metadata = {
            "n_batches": n_batches,
            "batch_files": batch_filenames,
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp_meta:
            local_meta = tmp_meta.name
            json.dump(metadata, tmp_meta, indent=2)

        try:
            faasr_put_file(
                local_file=local_meta,
                remote_folder=folder,
                remote_file=output2,
            )
            faasr_log(f"split: uploaded metadata → '{output2}'")
        finally:
            if os.path.exists(local_meta):
                os.remove(local_meta)

        faasr_log("split: done")

    finally:
        if os.path.exists(local_corpus):
            os.remove(local_corpus)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---