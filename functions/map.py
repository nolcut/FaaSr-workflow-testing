import json
import os
import tempfile
from collections import Counter


def map(folder: str, input1: str, input2: str, output1: str) -> None:
    # Determine this instance's rank (1..3)
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"map: starting — folder={folder}, rank={rank}/{r['max_rank']}")

    # Resolve rank-specific filenames
    batch_file = input1.format(rank=rank)
    manifest_file = input2  # no {rank} placeholder in manifest
    partial_counts_file = output1.format(rank=rank)

    # Download the split manifest (metadata, no rank placeholder)
    fd, local_manifest = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        faasr_get_file(
            local_file=local_manifest,
            remote_folder=folder,
            remote_file=manifest_file,
        )
    except Exception as e:
        faasr_log(f"map: ERROR — could not retrieve manifest {manifest_file}: {e}")
        raise

    try:
        with open(local_manifest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        faasr_log(
            f"map: manifest loaded — total_batches={manifest.get('total_batches')}"
        )
    except Exception as e:
        faasr_log(f"map: ERROR — could not parse manifest {manifest_file}: {e}")
        raise
    finally:
        if os.path.exists(local_manifest):
            os.remove(local_manifest)

    # Download the text batch assigned to this rank
    fd, local_batch = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        faasr_get_file(
    # --- CONTRACT: requires ---
    if "split_manifest.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Split manifest must exist in S3 before map can run")
        raise SystemExit(1)
    if "split_manifest.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Split manifest must be non-empty so map can read batch metadata")
        raise SystemExit(1)
    if "batch_{rank}.txt".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Rank-specific batch file must exist in S3 for this map instance to process")
        raise SystemExit(1)
    if "batch_{rank}.txt".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Rank-specific batch file should contain words for meaningful word counting")
        raise SystemExit(1)
    # --- end requires ---
            local_file=local_batch,
            remote_folder=folder,
            remote_file=batch_file,
        )
    except Exception as e:
        faasr_log(
            f"map: ERROR — could not retrieve batch file {batch_file}: {e}"
        )
        raise

    # Read and tokenize words (split wrote one word per line via "\n".join)
    try:
        with open(local_batch, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        faasr_log(f"map: ERROR — could not read local batch file: {e}")
        raise
    finally:
        if os.path.exists(local_batch):
            os.remove(local_batch)

    words = text.split()
    faasr_log(f"map: rank={rank} — {len(words)} words loaded from {batch_file}")

    if not words:
        faasr_log(
            f"map: WARNING — batch file {batch_file} is empty; "
            "producing empty partial counts"
        )

    # Count word occurrences for this batch
    counts = dict(Counter(words))
    faasr_log(
        f"map: rank={rank} — {len(counts)} unique words counted in {batch_file}"
    )

    # Write partial counts to a local temp file and upload to S3
    fd, local_output = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(counts, f)
        faasr_put_file(
    # --- CONTRACT: promises ---
    if "partial_counts_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Map must upload partial word counts JSON to S3 for the reduce step")
        raise SystemExit(1)
    if "partial_counts_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Partial counts file must be non-empty (at minimum an empty JSON object)")
        raise SystemExit(1)
    # --- end promises ---
            local_file=local_output,
            remote_folder=folder,
            remote_file=partial_counts_file,
        )
    except Exception as e:
        faasr_log(
            f"map: ERROR — could not upload partial counts {partial_counts_file}: {e}"
        )
        raise
    finally:
        if os.path.exists(local_output):
            os.remove(local_output)

    faasr_log(
        f"map: rank={rank} — uploaded partial counts → {partial_counts_file}"
    )
    faasr_log(f"map: rank={rank} — complete")