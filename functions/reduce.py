import json
import os
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "shuffle_shard_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffle shard file for this reducer instance must exist in S3 before reduction can proceed")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "reduce_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Reducer output file for this instance must be present in S3 after reduction completes")
        raise SystemExit(1)
# --- end contract helpers ---
def reduce(folder: str, input1: str, output1: str) -> None:
    """
    Reads this reducer instance's assigned shuffle shard from S3, sums the
    partial counts for every word in the shard, and writes the final
    word-count results as a JSON file back to S3.

    The shuffle shard format is:
        { "word": [count_from_mapper_1, count_from_mapper_2, ...], ... }

    The output format is:
        { "word": total_count, ... }

    This function runs as one of 5 parallel instances.  faasr_rank() tells
    us which shard we own (rank 1‥5).
    """
    # ── 1. Determine this instance's rank ────────────────────────────────────
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"reduce instance rank={rank} (max_rank={r['max_rank']})")

    # ── 2. Resolve ranked filenames ──────────────────────────────────────────
    shard_file = input1.format(rank=rank)
    result_file = output1.format(rank=rank)

    # ── 3. Download the shuffle shard ────────────────────────────────────────
    local_shard = tempfile.mktemp(suffix=".json")
    faasr_log(f"Downloading shuffle shard '{shard_file}' from folder '{folder}'")
    faasr_get_file(local_file=local_shard, remote_folder=folder, remote_file=shard_file)

    with open(local_shard, "r", encoding="utf-8") as fh:
        shard = json.load(fh)
    os.unlink(local_shard)

    # ── 4. Validate shard format ─────────────────────────────────────────────
    if not isinstance(shard, dict):
        msg = (
            f"Unexpected format in '{shard_file}': expected a JSON object "
            f"(dict), got {type(shard).__name__}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"Shard {rank} contains {len(shard)} unique word(s)")

    # ── 5. Reduce: sum partial counts for each word ──────────────────────────
    final_counts: dict = {}
    for word, counts in shard.items():
        if not isinstance(counts, list):
            msg = (
                f"Unexpected counts format for word '{word}' in shard "
                f"{rank}: expected list, got {type(counts).__name__}"
            )
            faasr_log(msg)
            raise ValueError(msg)
        final_counts[word] = sum(counts)

    faasr_log(
        f"Reduced {len(final_counts)} word(s); "
        f"total tokens in shard: {sum(final_counts.values())}"
    )

    # ── 6. Write and upload the result ───────────────────────────────────────
    local_result = tempfile.mktemp(suffix=".json")
    with open(local_result, "w", encoding="utf-8") as fh:
        json.dump(final_counts, fh, indent=2, sort_keys=True)

    faasr_log(f"Uploading result '{result_file}' to folder '{folder}'")
    faasr_put_file(local_file=local_result, remote_folder=folder, remote_file=result_file)
    os.unlink(local_result)

    faasr_log(f"reduce rank={rank} complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---