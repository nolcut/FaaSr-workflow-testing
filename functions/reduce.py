import json
import os
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "shuffle_bucket_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffle bucket file for this rank must exist in S3 before the reducer can process it")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "reduce_result_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Reduce result file for this rank must have been uploaded to S3 after processing")
        raise SystemExit(1)
# --- end contract helpers ---
def reduce(folder: str, input1: str, output1: str) -> None:
    """
    Reads the shuffle bucket file assigned to this ranked reducer instance,
    sums all partial counts for each word in the bucket, and writes the final
    word frequencies for that partition to reduce_result_{rank}.json in S3.

    Parameters
    ----------
    folder  : S3 folder (remote_folder) for all I/O
    input1  : remote filename template for shuffle buckets, e.g. "shuffle_bucket_{rank}.json"
    output1 : remote filename template for reduce results, e.g. "reduce_result_{rank}.json"
    """

    # ------------------------------------------------------------------ #
    # 1. Determine this instance's rank                                    #
    # ------------------------------------------------------------------ #
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"reduce: rank {rank}/{r['max_rank']} starting")

    # ------------------------------------------------------------------ #
    # 2. Resolve filenames for this rank                                   #
    # ------------------------------------------------------------------ #
    remote_input = input1.format(rank=rank)
    remote_output = output1.format(rank=rank)

    faasr_log(f"reduce: reading '{remote_input}' from folder '{folder}'")

    # ------------------------------------------------------------------ #
    # 3. Download the shuffle bucket file                                  #
    # ------------------------------------------------------------------ #
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp_in:
        local_input = tmp_in.name

    try:
        faasr_get_file(
            local_file=local_input,
            remote_folder=folder,
            remote_file=remote_input,
        )

        if not os.path.exists(local_input) or os.path.getsize(local_input) == 0:
            msg = (
                f"reduce: shuffle bucket file '{remote_input}' is missing or empty "
                f"in folder '{folder}'"
            )
            faasr_log(msg)
            raise RuntimeError(msg)

        with open(local_input, "r", encoding="utf-8") as fh:
            bucket = json.load(fh)

    finally:
        if os.path.exists(local_input):
            os.remove(local_input)

    faasr_log(f"reduce: loaded {len(bucket)} unique word(s) from '{remote_input}'")

    # ------------------------------------------------------------------ #
    # 4. Sum partial counts for each word                                  #
    # ------------------------------------------------------------------ #
    # bucket format: {word: [partial_count_a, partial_count_b, ...]}
    word_totals: dict = {}
    for word, counts in bucket.items():
        if not isinstance(counts, list):
            msg = (
                f"reduce: unexpected format for word '{word}' in '{remote_input}': "
                f"expected list of counts, got {type(counts).__name__}"
            )
            faasr_log(msg)
            raise RuntimeError(msg)
        word_totals[word] = sum(counts)

    faasr_log(
        f"reduce: computed total counts for {len(word_totals)} word(s)"
    )

    # ------------------------------------------------------------------ #
    # 5. Write the result and upload to S3                                 #
    # ------------------------------------------------------------------ #
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp_out:
        local_output = tmp_out.name
        json.dump(word_totals, tmp_out, indent=2)

    try:
        faasr_put_file(
            local_file=local_output,
            remote_folder=folder,
            remote_file=remote_output,
        )
        faasr_log(f"reduce: uploaded result → '{remote_output}'")
    finally:
        if os.path.exists(local_output):
            os.remove(local_output)

    faasr_log(f"reduce: rank {rank} done")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---