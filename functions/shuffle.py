import json
import os
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "split_metadata.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Split metadata file must exist in S3 before shuffle can determine the number of map batches")
        raise SystemExit(1)
# --- end contract helpers ---
def shuffle(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Reads all N partial word-count JSON files produced by the map phase and the
    split_metadata.json to discover N. Merges word counts into a per-word
    structure and partitions words across M=5 reducer buckets. Writes M
    shuffle output JSON files (shuffle_bucket_1.json … shuffle_bucket_M.json),
    each containing a dict mapping words to their list of partial counts.

    Parameters
    ----------
    folder  : S3 folder (remote_folder) for all I/O
    input1  : remote filename template for map results, e.g. "map_result_{rank}.json"
    input2  : remote filename for split metadata, e.g. "split_metadata.json"
    output1 : remote filename template for shuffle buckets, e.g. "shuffle_bucket_{rank}.json"
    """

    # ------------------------------------------------------------------ #
    # 1. Read split_metadata.json to discover N (number of map batches)   #
    # ------------------------------------------------------------------ #
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp_meta:
        local_meta = tmp_meta.name

    try:
        faasr_get_file(
            local_file=local_meta,
            remote_folder=folder,
            remote_file=input2,
        )

        if not os.path.exists(local_meta) or os.path.getsize(local_meta) == 0:
            msg = f"shuffle: metadata file '{input2}' is missing or empty in folder '{folder}'"
            faasr_log(msg)
            raise RuntimeError(msg)

        with open(local_meta, "r", encoding="utf-8") as fh:
            metadata = json.load(fh)
    finally:
        if os.path.exists(local_meta):
            os.remove(local_meta)

    n_batches = metadata.get("n_batches")
    if n_batches is None:
        msg = f"shuffle: 'n_batches' key missing from metadata file '{input2}'"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_log(f"shuffle: metadata reports {n_batches} map batch(es)")

    # ------------------------------------------------------------------ #
    # 2. Discover all map result files via faasr_get_folder_list           #
    # ------------------------------------------------------------------ #
    # The map outputs follow the template input1 (e.g. "map_result_{rank}.json").
    # Derive the prefix and suffix to filter the folder listing.
    map_prefix = input1.split("{rank}")[0]   # "map_result_"
    map_suffix = input1.split("{rank}")[-1]   # ".json"

    all_names = faasr_get_folder_list(prefix=folder)

    # faasr_get_folder_list may return "folder/filename" paths — take the basename
    map_result_files = sorted(
        name.rsplit("/", 1)[-1]
        for name in all_names
        if name.rsplit("/", 1)[-1].startswith(map_prefix)
        and name.rsplit("/", 1)[-1].endswith(map_suffix)
    )

    if not map_result_files:
        msg = (
            f"shuffle: no map result files matching pattern '{input1}' "
            f"found in folder '{folder}'"
        )
        faasr_log(msg)
        raise RuntimeError(msg)

    if len(map_result_files) != n_batches:
        faasr_log(
            f"shuffle: WARNING — expected {n_batches} map result file(s) from metadata "
            f"but discovered {len(map_result_files)}: {map_result_files}"
        )

    faasr_log(f"shuffle: discovered {len(map_result_files)} map result file(s): {map_result_files}")

    # ------------------------------------------------------------------ #
    # 3. Read all map result files and aggregate per-word partial counts   #
    # ------------------------------------------------------------------ #
    # Each map_result_{rank}.json is a dict {word: count (int)}.
    # We build {word: [count_from_mapper_a, count_from_mapper_b, ...]}
    word_partial_counts: dict = {}

    for map_file in map_result_files:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp_map:
            local_map = tmp_map.name

        try:
            faasr_get_file(
                local_file=local_map,
                remote_folder=folder,
                remote_file=map_file,
            )

            if not os.path.exists(local_map) or os.path.getsize(local_map) == 0:
                msg = f"shuffle: map result file '{map_file}' is missing or empty in folder '{folder}'"
                faasr_log(msg)
                raise RuntimeError(msg)

            with open(local_map, "r", encoding="utf-8") as fh:
                partial_counts = json.load(fh)

            faasr_log(
                f"shuffle: read {len(partial_counts)} unique word(s) from '{map_file}'"
            )

            for word, count in partial_counts.items():
                if word not in word_partial_counts:
                    word_partial_counts[word] = []
                word_partial_counts[word].append(count)

        finally:
            if os.path.exists(local_map):
                os.remove(local_map)

    faasr_log(
        f"shuffle: aggregated {len(word_partial_counts)} unique word(s) across all mappers"
    )

    # ------------------------------------------------------------------ #
    # 4. Partition words across M reducer buckets                          #
    # ------------------------------------------------------------------ #
    # M is fixed by the workflow fan-out to the reduce step (5 parallel instances).
    # Use consistent hash partitioning within this process:
    #   bucket_rank = hash(word) % n_reducers + 1  (Python % is always non-negative)
    n_reducers = 5

    buckets: dict = {rank: {} for rank in range(1, n_reducers + 1)}

    for word, counts in word_partial_counts.items():
        bucket_rank = (hash(word) % n_reducers) + 1
        buckets[bucket_rank][word] = counts

    for rank in range(1, n_reducers + 1):
        faasr_log(f"shuffle: bucket {rank} contains {len(buckets[rank])} unique word(s)")

    # ------------------------------------------------------------------ #
    # 5. Write and upload each shuffle bucket file                         #
    # ------------------------------------------------------------------ #
    for rank in range(1, n_reducers + 1):
        remote_output = output1.replace("{rank}", str(rank))

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp_out:
            local_output = tmp_out.name
            json.dump(buckets[rank], tmp_out, indent=2)

        try:
            faasr_put_file(
                local_file=local_output,
                remote_folder=folder,
                remote_file=remote_output,
            )
            faasr_log(f"shuffle: uploaded bucket {rank}/{n_reducers} → '{remote_output}'")
        finally:
            if os.path.exists(local_output):
                os.remove(local_output)

    faasr_log("shuffle: done")