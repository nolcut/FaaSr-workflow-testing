import os
import json
import tempfile


def reduce(folder: str, input1: str, output1: str) -> None:
    """
    Ranked reduce step (5 parallel instances).

    Each instance:
      1. Resolves its shard number from faasr_rank().
      2. Downloads shuffle_result_{rank}.json — a JSON object mapping each
         assigned word to a list of partial counts (one per mapper that saw it).
      3. Sums the partial counts for every word in the shard.
      4. Uploads reduce_result_{rank}.json — a JSON object mapping each word
         to its total occurrence count across the entire input corpus.
    """

    # ── Determine this instance's rank ────────────────────────────────────────
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"reduce[{rank}/{r['max_rank']}]: starting")

    # ── Resolve shard-specific filenames ──────────────────────────────────────
    input_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    faasr_log(f"reduce[{rank}]: input='{input_file}', output='{output_file}'")

    # ── Download the shuffle shard for this reducer ───────────────────────────
    tmp_dir = tempfile.mkdtemp(prefix="faasr_reduce_")
    local_input = os.path.join(tmp_dir, input_file)

    faasr_log(f"reduce[{rank}]: downloading '{input_file}' from folder '{folder}'")
    faasr_get_file(
    # --- CONTRACT: requires ---
    if "shuffle_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffle shard file shuffle_result_{rank}.json must exist in S3 before reduce can run")
        raise SystemExit(1)
    if "shuffle_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffle shard file shuffle_result_{rank}.json must be non-empty — an empty file cannot be parsed as a valid word-to-counts JSON object")
        raise SystemExit(1)
    # --- end requires ---
        local_file=local_input,
        remote_folder=folder,
        remote_file=input_file,
    )

    # ── Load and validate ─────────────────────────────────────────────────────
    with open(local_input, "r", encoding="utf-8") as fh:
        shard: dict = json.load(fh)

    if not isinstance(shard, dict):
        msg = (
            f"reduce[{rank}]: '{input_file}' must be a JSON object "
            f"(word → list of counts), got {type(shard)}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    os.remove(local_input)
    faasr_log(f"reduce[{rank}]: loaded {len(shard)} words from '{input_file}'")

    # ── Aggregate partial counts ──────────────────────────────────────────────
    result: dict[str, int] = {}

    for word, partial_counts in shard.items():
        if not isinstance(partial_counts, list):
            msg = (
                f"reduce[{rank}]: expected a list of counts for word '{word}', "
                f"got {type(partial_counts)}"
            )
            faasr_log(msg)
            raise ValueError(msg)
        result[word] = sum(int(c) for c in partial_counts)

    faasr_log(
        f"reduce[{rank}]: aggregated {len(result)} words, "
        f"total tokens = {sum(result.values())}"
    )

    # ── Write and upload the result ───────────────────────────────────────────
    local_output = os.path.join(tmp_dir, output_file)

    with open(local_output, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False)

    faasr_put_file(
    # --- CONTRACT: promises ---
    if "reduce_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Reduce output file reduce_result_{rank}.json must exist in S3 after the reducer completes")
        raise SystemExit(1)
    if "reduce_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(faasr_prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Reduce output file reduce_result_{rank}.json must be non-empty — it should contain the aggregated word counts for this shard")
        raise SystemExit(1)
    # --- end promises ---
        local_file=local_output,
        remote_folder=folder,
        remote_file=output_file,
    )
    faasr_log(f"reduce[{rank}]: uploaded '{output_file}' → folder '{folder}'")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    os.remove(local_output)
    os.rmdir(tmp_dir)
    faasr_log(f"reduce[{rank}]: complete")