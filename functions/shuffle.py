import json
import os
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "manifest.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: manifest.json must be present in S3 before shuffle can run — it provides the number of mapper batches")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "shuffle_shard_1.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: shuffle_shard_1.json was not found in S3 after shuffle completed — reducer shard 1 was not uploaded")
        raise SystemExit(1)
    if "shuffle_shard_2.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: shuffle_shard_2.json was not found in S3 after shuffle completed — reducer shard 2 was not uploaded")
        raise SystemExit(1)
    if "shuffle_shard_3.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: shuffle_shard_3.json was not found in S3 after shuffle completed — reducer shard 3 was not uploaded")
        raise SystemExit(1)
    if "shuffle_shard_4.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: shuffle_shard_4.json was not found in S3 after shuffle completed — reducer shard 4 was not uploaded")
        raise SystemExit(1)
    if "shuffle_shard_5.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: shuffle_shard_5.json was not found in S3 after shuffle completed — reducer shard 5 was not uploaded")
        raise SystemExit(1)
# --- end contract helpers ---
def shuffle(folder: str, input1: str, input2: str, output1: str) -> None:
    """
    Reads all intermediate word count JSON files produced by all mapper instances
    from S3. Merges them into a grouped structure keyed by word where each value is
    a list of partial counts (one per mapper), then partitions this grouped structure
    into 5 reducer shards and writes one shuffle shard file per reducer to S3.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    NUM_REDUCERS = 5  # fan-out to reduce (×5); THIS function is unranked — hardcode 5

    # ── 1. Download and parse manifest ───────────────────────────────────────
    local_manifest = tempfile.mktemp(suffix=".json")
    faasr_log(f"Downloading manifest '{input2}' from folder '{folder}'")
    faasr_get_file(local_file=local_manifest, remote_folder=folder, remote_file=input2)

    with open(local_manifest, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    os.unlink(local_manifest)

    num_batches = manifest.get("num_batches")

    # ── 2. Determine map result files to fetch ───────────────────────────────
    # Primary: use num_batches from manifest to fetch exactly the right files.
    # Fallback: discover via folder listing when manifest lacks the count.
    if num_batches is not None:
        faasr_log(f"Manifest reports {num_batches} mapper batch(es); fetching ranks 1..{num_batches}")
        map_result_files = [
            input1.replace("{rank}", str(i)) for i in range(1, num_batches + 1)
        ]
        faasr_log(f"Map result files to fetch: {map_result_files}")
    else:
        faasr_log(
            f"Manifest does not contain 'num_batches'; "
            f"discovering map result files via folder listing in '{folder}'"
        )
        all_files = faasr_get_folder_list(prefix=folder)
        map_result_files = sorted(
            f.rsplit("/", 1)[-1]
            for f in all_files
            if f.rsplit("/", 1)[-1].startswith("map_result_")
            and f.rsplit("/", 1)[-1].endswith(".json")
        )
        faasr_log(f"Discovered {len(map_result_files)} map result file(s): {map_result_files}")

    if not map_result_files:
        msg = (
            f"No map_result_*.json files to process for folder '{folder}' — "
            "cannot shuffle; ensure all map instances have completed"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # ── 3. Download and merge all mapper outputs ──────────────────────────────
    # merged: { word: [count_from_mapper_A, count_from_mapper_B, ...] }
    merged: dict = {}

    for map_file in map_result_files:
        local_map = tempfile.mktemp(suffix=".json")
        faasr_log(f"Downloading '{map_file}' from folder '{folder}'")
        faasr_get_file(local_file=local_map, remote_folder=folder, remote_file=map_file)

        with open(local_map, "r", encoding="utf-8") as fh:
            word_counts = json.load(fh)
        os.unlink(local_map)

        for word, count in word_counts.items():
            if word not in merged:
                merged[word] = []
            merged[word].append(count)

    faasr_log(
        f"Merged {len(merged)} unique word(s) from {len(map_result_files)} mapper(s)"
    )

    # ── 4. Partition words into NUM_REDUCERS shards ───────────────────────────
    # Use Python's built-in hash for consistent within-process word assignment.
    # Each word maps to exactly one shard; shards are disjoint and cover all words.
    shards: list = [{} for _ in range(NUM_REDUCERS)]
    for word, counts in merged.items():
        shard_idx = hash(word) % NUM_REDUCERS
        shards[shard_idx][word] = counts

    for idx, shard in enumerate(shards, start=1):
        faasr_log(f"Shard {idx}: {len(shard)} word(s)")

    # ── 5. Write and upload each reducer shard ────────────────────────────────
    for i in range(1, NUM_REDUCERS + 1):
        local_shard = tempfile.mktemp(suffix=".json")
        with open(local_shard, "w", encoding="utf-8") as fh:
            json.dump(shards[i - 1], fh, indent=2, sort_keys=True)

        remote_shard = output1.replace("{rank}", str(i))
        faasr_log(f"Uploading shuffle shard '{remote_shard}' to folder '{folder}'")
        faasr_put_file(
            local_file=local_shard, remote_folder=folder, remote_file=remote_shard
        )
        os.unlink(local_shard)

    faasr_log("shuffle complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---