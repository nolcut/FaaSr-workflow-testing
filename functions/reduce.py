import json
import os
import tempfile


def reduce(folder: str, input1: str, output1: str) -> None:
    """
    Reduce phase of MapReduce word count.

    Reads the shuffled partition file for this reducer instance, sums all
    partial counts per word, and writes the final word frequency JSON file.

    Parameters
    ----------
    folder  : S3 folder (prefix) for all FaaSr I/O.
    input1  : Filename template for shuffled partition files,
              e.g. "shuffled_{rank}.json".
    output1 : Filename template for final word-count output,
              e.g. "word_counts_{rank}.json".
    """
    # ------------------------------------------------------------------ #
    # 1. Determine this instance's rank                                    #
    # ------------------------------------------------------------------ #
    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"reduce[{rank}]: starting (max_rank={r['max_rank']})")

    # Substitute rank into the filename templates
    remote_input = input1.format(rank=rank)
    remote_output = output1.format(rank=rank)

    # ------------------------------------------------------------------ #
    # 2. Download the shuffled partition for this reducer                  #
    # ------------------------------------------------------------------ #
    local_in = tempfile.mktemp(suffix=".json")
    faasr_log(f"reduce[{rank}]: downloading {folder}/{remote_input}")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_input)
    # --- CONTRACT: requires ---
    if not os.path.exists("shuffled_{rank}.json"):
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffled partition file for this reducer rank must exist on S3 before reduce can run")
        raise SystemExit(1)
    if not os.path.exists("shuffled_{rank}.json") or os.path.getsize("shuffled_{rank}.json") == 0:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffled partition file must not be empty; an empty file yields no word counts to aggregate")
        raise SystemExit(1)
    try:
        import json as _json; _json.loads(open("shuffled_{rank}.json").read())
    except Exception as _e:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Shuffled partition file must be valid JSON mapping words to lists of partial counts: " + str(_e))
        raise SystemExit(1)
    # --- end requires ---

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"reduce[{rank}]: input file {remote_input} is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    with open(local_in, "r", encoding="utf-8") as fh:
        shuffled: dict = json.load(fh)
    os.remove(local_in)

    faasr_log(f"reduce[{rank}]: loaded {len(shuffled)} unique word(s) from {remote_input}")

    # ------------------------------------------------------------------ #
    # 3. Sum partial counts for each word                                  #
    # shuffled[word] = [count_from_mapper_1, count_from_mapper_2, ...]     #
    # ------------------------------------------------------------------ #
    word_totals: dict = {}
    for word, counts in shuffled.items():
        if not isinstance(counts, list):
            msg = (
                f"reduce[{rank}]: unexpected value type for word '{word}': "
                f"expected list, got {type(counts).__name__}"
            )
            faasr_log(msg)
            raise TypeError(msg)
        word_totals[word] = sum(counts)

    faasr_log(
        f"reduce[{rank}]: aggregated {len(word_totals)} word(s); "
        f"total tokens = {sum(word_totals.values())}"
    )

    # ------------------------------------------------------------------ #
    # 4. Write and upload the final word-frequency JSON                    #
    # ------------------------------------------------------------------ #
    local_out = tempfile.mktemp(suffix=".json")
    with open(local_out, "w", encoding="utf-8") as fh:
        json.dump(word_totals, fh, indent=2, sort_keys=True)

    faasr_log(f"reduce[{rank}]: uploading {folder}/{remote_output}")
    # --- CONTRACT: promises ---
    if not os.path.exists("word_counts_{rank}.json"):
        faasr_log("[PROMISE] CONTRACT VIOLATION: Reduced word-count output file must exist on S3 after successful completion")
        raise SystemExit(1)
    if not os.path.exists("word_counts_{rank}.json") or os.path.getsize("word_counts_{rank}.json") == 0:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Reduced word-count output file must not be empty; it should contain at least one aggregated word entry")
        raise SystemExit(1)
    # INPUTS_UNCHANGED: shuffled_{rank}.json (tracked at require time)
    # --- end promises ---
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_output)
    os.remove(local_out)

    faasr_log(f"reduce[{rank}]: complete → {remote_output}")