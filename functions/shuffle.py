import json
import os
import tempfile

# Number of parallel reduce instances (fan-out target)
NUM_REDUCERS = 5


def shuffle(folder: str, input1: str, input2: str, output1: str) -> None:
    """Collect all partial word-count JSON files from N mapper instances,
    group each word's counts into a list, partition by word across
    NUM_REDUCERS shards, and upload one shard file per reduce instance.

    Args:
        folder:  S3 folder holding all workflow files
        input1:  template name of mapper outputs, e.g. "partial_counts_{rank}.json"
        input2:  manifest filename, e.g. "split_manifest.json"
        output1: base output name,  e.g. "shuffled_counts.json"
                 → produces shuffled_counts_1.json … shuffled_counts_5.json
    """
    faasr_log(f"shuffle: starting — folder={folder}")

    # ------------------------------------------------------------------ #
    # Step 1: Download the split manifest to read total_batches metadata  #
    # ------------------------------------------------------------------ #
    fd, local_manifest = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        faasr_get_file(local_file=local_manifest, remote_folder=folder, remote_file=input2)
    except Exception as e:
        faasr_log(f"shuffle: ERROR — could not retrieve manifest {input2}: {e}")
        raise

    try:
        with open(local_manifest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        total_batches = manifest.get("total_batches")
        faasr_log(f"shuffle: manifest loaded — total_batches={total_batches}")
    except Exception as e:
        faasr_log(f"shuffle: ERROR — could not parse manifest {input2}: {e}")
        raise
    finally:
        if os.path.exists(local_manifest):
            os.remove(local_manifest)

    # ------------------------------------------------------------------ #
    # Step 2: Discover all partial-count files via faasr_get_folder_list  #
    # ------------------------------------------------------------------ #
    # The base prefix is everything in input1 before the {rank} token
    # e.g. "partial_counts_{rank}.json" → base_prefix = "partial_counts_"
    base_prefix = input1.split("{rank}")[0]   # "partial_counts_"

    all_remote = faasr_get_folder_list(faasr_prefix=folder)
    # Real FaaSr may return "folder/filename"; strip to bare filename
    partial_files = sorted(
        f.rsplit("/", 1)[-1]
        for f in all_remote
        if f.rsplit("/", 1)[-1].startswith(base_prefix)
        and f.rsplit("/", 1)[-1].endswith(".json")
    )

    faasr_log(
        f"shuffle: discovered {len(partial_files)} partial-count file(s): {partial_files}"
    )

    if not partial_files:
        msg = (
            f"shuffle: ERROR — no partial-count files found "
            f"matching prefix '{base_prefix}' in folder '{folder}'"
        )
        faasr_log(msg)
        raise RuntimeError(msg)

    # ------------------------------------------------------------------ #
    # Step 3: Download each partial-count file and merge into grouped     #
    #         structure  {word: [count_from_mapper1, count_from_mapper2,  #
    #         …]}                                                          #
    # ------------------------------------------------------------------ #
    grouped_counts: dict[str, list] = {}

    for pf in partial_files:
        fd, local_partial = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            faasr_get_file(local_file=local_partial, remote_folder=folder, remote_file=pf)
    # --- CONTRACT: requires ---
    if "split_manifest.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Manifest file 'split_manifest.json' must exist in S3 before shuffle can determine total_batches")
        raise SystemExit(1)
    if "split_manifest.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Manifest file 'split_manifest.json' must be non-empty so shuffle can parse total_batches metadata")
        raise SystemExit(1)
    # EXISTS skipped: "partial_counts_{rank}.json" is a per-rank family on a non-ranked function (cannot verify a single name)
    # --- end requires ---
        except Exception as e:
            faasr_log(f"shuffle: ERROR — could not retrieve {pf}: {e}")
            raise

        try:
            with open(local_partial, "r", encoding="utf-8") as f:
                partial_counts = json.load(f)
        except Exception as e:
            faasr_log(f"shuffle: ERROR — could not parse {pf}: {e}")
            raise
        finally:
            if os.path.exists(local_partial):
                os.remove(local_partial)

        for word, count in partial_counts.items():
            if word not in grouped_counts:
                grouped_counts[word] = []
            grouped_counts[word].append(count)

        faasr_log(f"shuffle: merged {len(partial_counts)} word(s) from {pf}")

    faasr_log(f"shuffle: {len(grouped_counts)} unique word(s) grouped across all mappers")

    # ------------------------------------------------------------------ #
    # Step 4: Hash-partition words across NUM_REDUCERS shards             #
    # ------------------------------------------------------------------ #
    # Use sum-of-ordinals for a deterministic, PYTHONHASHSEED-independent
    # partition that is stable across any Python process.
    shards: list[dict] = [{} for _ in range(NUM_REDUCERS)]
    for word, counts in grouped_counts.items():
        shard_idx = sum(ord(c) for c in word) % NUM_REDUCERS
        shards[shard_idx][word] = counts

    # ------------------------------------------------------------------ #
    # Step 5: Upload one shard file per reduce instance                   #
    # ------------------------------------------------------------------ #
    # Derive shard filenames from output1:
    #   "shuffled_counts.json" → "shuffled_counts_1.json" … "shuffled_counts_5.json"
    if "." in output1:
        base_name, ext = output1.rsplit(".", 1)
    else:
        base_name, ext = output1, "json"

    for rank in range(1, NUM_REDUCERS + 1):
        shard_filename = f"{base_name}_{rank}.{ext}"   # e.g. shuffled_counts_1.json
        shard_data = shards[rank - 1]

        fd, local_shard = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(shard_data, f)
            faasr_put_file(
    # --- CONTRACT: promises ---
    if "shuffled_counts_1.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffle must produce shard file 'shuffled_counts_1.json' in S3 for reducer instance 1")
        raise SystemExit(1)
    if "shuffled_counts_2.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffle must produce shard file 'shuffled_counts_2.json' in S3 for reducer instance 2")
        raise SystemExit(1)
    if "shuffled_counts_3.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffle must produce shard file 'shuffled_counts_3.json' in S3 for reducer instance 3")
        raise SystemExit(1)
    if "shuffled_counts_4.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffle must produce shard file 'shuffled_counts_4.json' in S3 for reducer instance 4")
        raise SystemExit(1)
    if "shuffled_counts_5.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffle must produce shard file 'shuffled_counts_5.json' in S3 for reducer instance 5")
        raise SystemExit(1)
    # --- end promises ---
                local_file=local_shard,
                remote_folder=folder,
                remote_file=shard_filename,
            )
        except Exception as e:
            faasr_log(
                f"shuffle: ERROR — could not upload shard {shard_filename}: {e}"
            )
            raise
        finally:
            if os.path.exists(local_shard):
                os.remove(local_shard)

        faasr_log(
            f"shuffle: uploaded shard {rank}/{NUM_REDUCERS} "
            f"({len(shard_data)} word(s)) → {shard_filename}"
        )

    faasr_log("shuffle: complete")