import json
import os
import tempfile


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "shuffle_bucket_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffle bucket file for this rank must exist in S3 before reduction can begin")
        raise SystemExit(1)
def _faasr_promises(folder):
    if "word_counts_{rank}.json".format(rank=faasr_rank()["rank"]) not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Reduced word counts file for this rank must have been uploaded to S3 after reduction completes")
        raise SystemExit(1)
# --- end contract helpers ---
def reduce(folder: str, input1: str, output1: str) -> None:
    """
    Ranked reducer (1..5): reads its assigned shuffle bucket JSON from S3,
    sums all partial counts per word, and writes the final word-frequency
    JSON back to S3.

    Input  (from shuffle): shuffle_bucket_{rank}.json
           format: { word: [count1, count2, ...] }
    Output (sink node):    word_counts_{rank}.json
           format: { word: total_count }
    """
    # Determine which shard this instance owns
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    r = faasr_rank()
    rank = r["rank"]

    ranked_input = input1.format(rank=rank)
    ranked_output = output1.format(rank=rank)

    faasr_log(
        f"reduce[{rank}]: starting — reading '{ranked_input}' from folder '{folder}'"
    )

    # --- Download the shuffle bucket assigned to this rank ---
    local_in = tempfile.mktemp(suffix=".json")
    try:
        faasr_get_file(
            local_file=local_in, remote_folder=folder, remote_file=ranked_input
        )
    except Exception as exc:
        msg = (
            f"reduce[{rank}]: failed to download '{ranked_input}' "
            f"from folder '{folder}': {exc}"
        )
        faasr_log(f"ERROR: {msg}")
        raise

    # --- Parse: expect { word: [count, ...] } ---
    try:
        with open(local_in, "r", encoding="utf-8") as fh:
            bucket_data = json.load(fh)
    except Exception as exc:
        msg = f"reduce[{rank}]: failed to parse '{ranked_input}': {exc}"
        faasr_log(f"ERROR: {msg}")
        raise
    finally:
        if os.path.exists(local_in):
            os.remove(local_in)

    if not isinstance(bucket_data, dict):
        msg = (
            f"reduce[{rank}]: expected a JSON object in '{ranked_input}', "
            f"got {type(bucket_data).__name__}"
        )
        faasr_log(f"ERROR: {msg}")
        raise ValueError(msg)

    faasr_log(
        f"reduce[{rank}]: summing counts for {len(bucket_data)} unique word(s)"
    )

    # --- Sum partial counts: { word: [c1, c2, ...] } -> { word: total } ---
    word_totals: dict = {}
    for word, counts in bucket_data.items():
        if not isinstance(counts, list):
            msg = (
                f"reduce[{rank}]: malformed entry for word '{word}' in "
                f"'{ranked_input}' — expected list of counts, got "
                f"{type(counts).__name__}"
            )
            faasr_log(f"ERROR: {msg}")
            raise ValueError(msg)
        word_totals[word] = sum(counts)

    faasr_log(
        f"reduce[{rank}]: aggregation complete — "
        f"{len(word_totals)} word(s) totalled"
    )

    # --- Serialise and upload the final counts ---
    local_out = tempfile.mktemp(suffix=".json")
    try:
        with open(local_out, "w", encoding="utf-8") as fh:
            json.dump(word_totals, fh)

        faasr_put_file(
            local_file=local_out, remote_folder=folder, remote_file=ranked_output
        )
    except Exception as exc:
        msg = (
            f"reduce[{rank}]: failed to upload '{ranked_output}' "
            f"to folder '{folder}': {exc}"
        )
        faasr_log(f"ERROR: {msg}")
        raise
    finally:
        if os.path.exists(local_out):
            os.remove(local_out)

    faasr_log(
        f"reduce[{rank}]: complete — wrote '{ranked_output}' to folder '{folder}'"
    )
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---