import json
import os
import tempfile


def reduce(folder: str, input1: str, output1: str) -> None:
    """Reduce step: read this rank's shuffled shard, sum partial counts per word,
    and upload the final word totals as a JSON file.

    Args:
        folder:  S3 folder holding all workflow files
        input1:  base name of the shuffled shard files, e.g. "shuffled_counts.json"
                 → rank r reads  "shuffled_counts_{r}.json"
                 (same naming convention used by the upstream shuffle function)
        output1: output filename template, e.g. "final_counts_{rank}.json"
                 → rank r writes "final_counts_{r}.json"
    """
    # ------------------------------------------------------------------ #
    # Step 0: Determine this instance's rank                              #
    # ------------------------------------------------------------------ #
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"reduce: starting — folder={folder}, rank={rank}/{r['max_rank']}")

    # ------------------------------------------------------------------ #
    # Step 1: Derive rank-specific filenames                              #
    # ------------------------------------------------------------------ #
    # Shuffle uploads shard files as  "{base}_{rank}.{ext}"
    # e.g. "shuffled_counts.json"  →  "shuffled_counts_1.json"
    if "." in input1:
        base_name, ext = input1.rsplit(".", 1)
    else:
        base_name, ext = input1, "json"
    shard_filename = f"{base_name}_{rank}.{ext}"

    # Output template has an explicit {rank} placeholder
    output_filename = output1.format(rank=rank)

    faasr_log(
        f"reduce: rank={rank} — input shard: {shard_filename}, "
        f"output: {output_filename}"
    )

    # ------------------------------------------------------------------ #
    # Step 2: Download this rank's shuffled shard from S3                #
    # ------------------------------------------------------------------ #
    fd, local_shard = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        faasr_get_file(
    # --- CONTRACT: requires ---
    if "shuffled_counts.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffled shard file for this rank must exist in S3 before reduce can proceed")
        raise SystemExit(1)
    if "shuffled_counts.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffled shard file must be non-empty; an empty shard yields no word counts to reduce")
        raise SystemExit(1)
    # --- end requires ---
            local_file=local_shard,
            remote_folder=folder,
            remote_file=shard_filename,
        )
    except Exception as e:
        faasr_log(
            f"reduce: ERROR — could not retrieve shard {shard_filename}: {e}"
        )
        raise

    # ------------------------------------------------------------------ #
    # Step 3: Parse shard — format is {word: [count, count, ...]}        #
    # ------------------------------------------------------------------ #
    try:
        with open(local_shard, "r", encoding="utf-8") as f:
            shard_data = json.load(f)
    except Exception as e:
        faasr_log(f"reduce: ERROR — could not parse shard {shard_filename}: {e}")
        raise
    finally:
        if os.path.exists(local_shard):
            os.remove(local_shard)

    faasr_log(
        f"reduce: rank={rank} — {len(shard_data)} unique word(s) in shard"
    )

    # ------------------------------------------------------------------ #
    # Step 4: Sum partial counts → final total per word                  #
    # ------------------------------------------------------------------ #
    final_counts: dict[str, int] = {}
    for word, counts in shard_data.items():
        if isinstance(counts, list):
            final_counts[word] = sum(counts)
        else:
            # Defensive: handle a bare scalar if somehow already reduced
            final_counts[word] = int(counts)

    faasr_log(
        f"reduce: rank={rank} — computed final totals for "
        f"{len(final_counts)} word(s)"
    )

    # ------------------------------------------------------------------ #
    # Step 5: Write final counts to a temp file and upload to S3         #
    # ------------------------------------------------------------------ #
    fd, local_output = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(final_counts, f)
        faasr_put_file(
    # --- CONTRACT: promises ---
    if "final_counts_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Reduce must upload the final word-count file for this rank to S3")
        raise SystemExit(1)
    if "final_counts_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Final counts file must be non-empty; a missing or empty output indicates the reduce step failed to write results")
        raise SystemExit(1)
    # --- end promises ---
            local_file=local_output,
            remote_folder=folder,
            remote_file=output_filename,
        )
    except Exception as e:
        faasr_log(
            f"reduce: ERROR — could not upload {output_filename}: {e}"
        )
        raise
    finally:
        if os.path.exists(local_output):
            os.remove(local_output)

    faasr_log(
        f"reduce: rank={rank} — uploaded final counts → {output_filename}"
    )
    faasr_log(f"reduce: rank={rank} — complete")