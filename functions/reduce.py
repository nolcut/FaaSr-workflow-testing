import json
import os


def reduce(folder: str, input1: str, input2: str, output1: str) -> None:
    # This function is RANKED: each of the parallel instances handles only its
    # own assigned word/key, identified by its own rank (1..M).
    r = faasr_rank()
    rank = r["rank"]

    # --- Read the stable rank->word mapping to determine this reducer's key. ---
    local_map = "rank_word_map.json"
    faasr_get_file(local_file=local_map, remote_folder=folder, remote_file=input2)
    with open(local_map, "r") as f:
        rank_word_map = json.load(f)
    if not isinstance(rank_word_map, dict):
        raise ValueError(
            f"Expected a JSON object (rank->word) in {input2}, "
            f"got {type(rank_word_map).__name__}"
        )

    key = str(rank)
    if key not in rank_word_map:
        raise KeyError(
            f"[reduce rank {rank}] no word assigned to rank {rank} in {input2}; "
            f"available ranks: {sorted(rank_word_map.keys())}"
        )
    word = rank_word_map[key]

    # --- Read this reducer's flattened partial counts for its assigned word. ---
    remote_input = input1.format(rank=rank)
    local_input = f"word_counts_{rank}.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=remote_input)
    with open(local_input, "r") as f:
        partial_counts = json.load(f)
    if not isinstance(partial_counts, list):
        raise ValueError(
            f"Expected a JSON array of partial counts in {remote_input}, "
            f"got {type(partial_counts).__name__}"
        )

    faasr_log(
        f"[reduce rank {rank}] word '{word}': summing partial counts {partial_counts}"
    )

    # Sum all partial counts belonging to this word -> total occurrence count Zi.
    total = sum(partial_counts)

    result = {word: total}
    remote_output = output1.format(rank=rank)
    local_output = f"final_count_{rank}.json"
    with open(local_output, "w") as f:
        json.dump(result, f)
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=remote_output)
    faasr_log(
        f"[reduce rank {rank}] wrote final count {result} to {folder}/{remote_output}"
    )

    for p in (local_map, local_input, local_output):
        try:
            os.remove(p)
        except OSError:
            pass
