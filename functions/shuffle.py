import hashlib
import json
import os
import tempfile


def shuffle(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Shuffle phase of MapReduce word count.

    Collects all N partial word-count files produced by the map phase,
    merges them into per-word count lists, then writes M partition files
    for the M ranked reducer instances.

    Parameters
    ----------
    folder  : S3 folder (prefix) for all FaaSr I/O.
    input1  : Filename template for partial-count files,
              e.g. "partial_counts_{rank}.json".
    input2  : Metadata filename produced by split,
              e.g. "split_metadata.json".
    output1 : Filename template for shuffled partition outputs,
              e.g. "shuffled_{rank}.json".
    """
    # Number of reducer instances (fan-out to ranked `reduce` ×5)
    N_REDUCERS = 5

    # ------------------------------------------------------------------ #
    # 1. Download and parse split metadata                                 #
    # ------------------------------------------------------------------ #
    local_meta = tempfile.mktemp(suffix=".json")
    faasr_log(f"shuffle: downloading metadata {folder}/{input2}")
    faasr_get_file(local_file=local_meta, remote_folder=folder, remote_file=input2)

    with open(local_meta, "r", encoding="utf-8") as fh:
        metadata = json.load(fh)
    os.remove(local_meta)

    n_mappers = metadata.get("n_batches")
    if n_mappers is not None:
        faasr_log(
            f"shuffle: metadata reports {n_mappers} mapper(s); "
            f"{N_REDUCERS} reducer(s)"
        )
    else:
        faasr_log(
            "shuffle: metadata 'n_batches' not present; "
            "mapper count will be inferred from discovered files"
        )

    # ------------------------------------------------------------------ #
    # 2. Discover all partial-count files via folder listing               #
    # ------------------------------------------------------------------ #
    # Extract static prefix from the template, e.g. "partial_counts_{rank}.json"
    # → prefix = "partial_counts_"
    input1_prefix = input1.split("{rank}")[0]
    faasr_prefix_path = f"{folder}/{input1_prefix}"
    faasr_log(f"shuffle: listing files under prefix '{faasr_prefix_path}'")
    discovered = faasr_get_folder_list(faasr_prefix=faasr_prefix_path)
    faasr_log(f"shuffle: discovered {len(discovered)} file(s): {discovered}")

    if not discovered:
        msg = (
            f"shuffle: no partial-count files found with prefix '{input1_prefix}' "
            f"in folder '{folder}'"
        )
        faasr_log(msg)
        raise ValueError(msg)

    if n_mappers is not None and len(discovered) != n_mappers:
        faasr_log(
            f"shuffle: WARNING — metadata expected {n_mappers} file(s) "
            f"but {len(discovered)} were discovered"
        )

    # ------------------------------------------------------------------ #
    # 3. Download each partial-count file and merge into per-word lists    #
    # ------------------------------------------------------------------ #
    # word_counts[word] = [count_from_mapper_a, count_from_mapper_b, ...]
    word_counts: dict = {}

    for filename in sorted(discovered):
        local_part = tempfile.mktemp(suffix=".json")
        faasr_log(f"shuffle: downloading {folder}/{filename}")
        faasr_get_file(
    # --- CONTRACT: requires ---
    if not os.path.exists("split_metadata.json"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Metadata file split_metadata.json must exist in S3 before shuffle can run")
        raise SystemExit(1)
    if not os.path.exists("split_metadata.json") or os.path.getsize("split_metadata.json") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Metadata file split_metadata.json must not be empty")
        raise SystemExit(1)
    try:
        import json as _json; _json.loads(open("split_metadata.json").read())
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Metadata file split_metadata.json must be valid JSON: " + str(_e))
        raise SystemExit(1)
    if not os.path.exists("partial_counts_{rank}.json"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: At least one partial_counts_{rank}.json file must exist in S3 for shuffle to merge")
        raise SystemExit(1)
    if not os.path.exists("partial_counts_{rank}.json") or os.path.getsize("partial_counts_{rank}.json") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Each discovered partial_counts file must not be empty")
        raise SystemExit(1)
    try:
        import json as _json; _json.loads(open("partial_counts_{rank}.json").read())
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Each partial_counts_{rank}.json file must be valid JSON containing a word-count dictionary: " + str(_e))
        raise SystemExit(1)
    # --- end requires ---
            local_file=local_part, remote_folder=folder, remote_file=filename
        )

        with open(local_part, "r", encoding="utf-8") as fh:
            partial: dict = json.load(fh)
        os.remove(local_part)

        faasr_log(f"shuffle: {filename} → {len(partial)} unique word(s)")
        for word, count in partial.items():
            if word not in word_counts:
                word_counts[word] = []
            word_counts[word].append(count)

    faasr_log(
        f"shuffle: merged {len(word_counts)} unique word(s) "
        f"across {len(discovered)} mapper output(s)"
    )

    # ------------------------------------------------------------------ #
    # 4. Partition words across N_REDUCERS buckets (deterministic hashing) #
    # Use MD5 so assignment is independent of PYTHONHASHSEED.             #
    # ------------------------------------------------------------------ #
    partitions: list = [{} for _ in range(N_REDUCERS)]

    for word, counts in word_counts.items():
        digest = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        bucket = digest % N_REDUCERS
        partitions[bucket][word] = counts

    for i in range(N_REDUCERS):
        faasr_log(
            f"shuffle: partition {i + 1}/{N_REDUCERS} → {len(partitions[i])} word(s)"
        )

    # ------------------------------------------------------------------ #
    # 5. Write and upload one shuffled JSON file per reducer               #
    # ------------------------------------------------------------------ #
    for rank in range(1, N_REDUCERS + 1):
        shuffled_remote = output1.format(rank=rank)
        local_out = tempfile.mktemp(suffix=".json")
        with open(local_out, "w", encoding="utf-8") as fh:
            json.dump(partitions[rank - 1], fh, indent=2, sort_keys=True)
        faasr_log(
            f"shuffle: uploading partition {rank} → {folder}/{shuffled_remote}"
        )
    # --- CONTRACT: promises ---
    if not os.path.exists("shuffled_1.json"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffled partition file for reducer 1 must be uploaded to S3")
        raise SystemExit(1)
    if not os.path.exists("shuffled_2.json"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffled partition file for reducer 2 must be uploaded to S3")
        raise SystemExit(1)
    if not os.path.exists("shuffled_3.json"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffled partition file for reducer 3 must be uploaded to S3")
        raise SystemExit(1)
    if not os.path.exists("shuffled_4.json"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffled partition file for reducer 4 must be uploaded to S3")
        raise SystemExit(1)
    if not os.path.exists("shuffled_5.json"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffled partition file for reducer 5 must be uploaded to S3")
        raise SystemExit(1)
    if not os.path.exists("shuffled_1.json") or os.path.getsize("shuffled_1.json") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Shuffled partition 1 must contain at least one word entry")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: partial_counts_{rank}.json (tracked at require time)
    # INPUTS_UNCHANGED: split_metadata.json (tracked at require time)
    # --- end promises ---
        faasr_put_file(
            local_file=local_out,
            remote_folder=folder,
            remote_file=shuffled_remote,
        )
        os.remove(local_out)

    faasr_log("shuffle: complete")