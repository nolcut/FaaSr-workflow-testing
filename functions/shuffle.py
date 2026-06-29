import hashlib
import json
import os
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "split_metadata.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: split_metadata.json must exist in S3 before shuffle can determine the number of map batches")
        raise SystemExit(1)
# --- end contract helpers ---
def shuffle(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Read all partial word count JSON files from map workers, merge them,
    partition words into M=5 reducer buckets by deterministic hash, and write
    one shuffle_bucket_{rank}.json per bucket containing word -> [count1, count2, ...]
    for words assigned to that bucket.
    """

    # Fan-out to reduce is ×5 (hardcoded per CONTEXT.md — do NOT call faasr_rank() here)
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    M = 5

    # --- Download and parse split metadata ---
    faasr_log(f"shuffle: downloading split metadata '{input2}' from folder {folder}")
    local_meta = tempfile.mktemp(suffix=".json")
    faasr_get_file(local_file=local_meta, remote_folder=folder, remote_file=input2)

    with open(local_meta, "r", encoding="utf-8") as fh:
        metadata = json.load(fh)
    os.remove(local_meta)

    n_batches = metadata.get("n_batches")
    if n_batches is None:
        msg = (
            f"shuffle: required key 'n_batches' missing from '{input2}' — "
            f"got keys: {list(metadata.keys())}"
        )
        faasr_log(f"ERROR: {msg}")
        raise KeyError(msg)

    faasr_log(f"shuffle: split stage produced {n_batches} map batch(es)")

    # --- Discover partial count files written by map workers ---
    # Use faasr_get_folder_list to dynamically find all partial_counts_*.json files;
    # never assume a fixed count or use boto3.
    faasr_log(f"shuffle: listing partial count files in folder {folder}")
    all_names = faasr_get_folder_list(prefix=f"{folder}/partial_counts_")

    # Strip any folder prefix from returned names and keep only partial_counts_*.json
    partial_files = sorted([
        name.rsplit("/", 1)[-1]
        for name in all_names
        if name.rsplit("/", 1)[-1].startswith("partial_counts_")
        and name.rsplit("/", 1)[-1].endswith(".json")
    ])

    if not partial_files:
        msg = f"shuffle: no 'partial_counts_*.json' files found in folder {folder}"
        faasr_log(f"ERROR: {msg}")
        raise FileNotFoundError(msg)

    faasr_log(
        f"shuffle: discovered {len(partial_files)} partial count file(s): {partial_files}"
    )

    # --- Read all partial counts and partition words into M buckets ---
    # Each bucket maps: word -> list of counts (one entry per map worker that saw the word)
    buckets: list[dict] = [{} for _ in range(M)]

    for pc_filename in partial_files:
        faasr_log(f"shuffle: downloading {pc_filename} from folder {folder}")
        local_pc = tempfile.mktemp(suffix=".json")
        faasr_get_file(local_file=local_pc, remote_folder=folder, remote_file=pc_filename)

        with open(local_pc, "r", encoding="utf-8") as fh:
            word_counts = json.load(fh)
        os.remove(local_pc)

        if not isinstance(word_counts, dict):
            msg = (
                f"shuffle: '{pc_filename}' is not a JSON object — "
                f"expected dict{{word: count}}, got {type(word_counts).__name__}"
            )
            faasr_log(f"ERROR: {msg}")
            raise ValueError(msg)

        faasr_log(
            f"shuffle: partitioning {len(word_counts)} word(s) from {pc_filename}"
        )

        for word, count in word_counts.items():
            # Deterministic bucket assignment: MD5 hex digest modulo M
            bucket_idx = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % M
            if word not in buckets[bucket_idx]:
                buckets[bucket_idx][word] = []
            buckets[bucket_idx][word].append(count)

    # --- Write and upload one shuffle bucket file per reducer instance ---
    for i in range(1, M + 1):
        bucket_data = buckets[i - 1]
        remote_output = output1.replace("{rank}", str(i))

        local_out = tempfile.mktemp(suffix=".json")
        with open(local_out, "w", encoding="utf-8") as fh:
            json.dump(bucket_data, fh)

        faasr_log(
            f"shuffle: uploading bucket {i}/{M} "
            f"({len(bucket_data)} unique word(s)) → {remote_output}"
        )
        faasr_put_file(
            local_file=local_out, remote_folder=folder, remote_file=remote_output
        )
        os.remove(local_out)

    faasr_log(
        f"shuffle: complete — wrote {M} shuffle buckets to folder {folder} for reduce"
    )