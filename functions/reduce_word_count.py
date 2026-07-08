import os
import json


def reduce_word_count(folder: str, input1: str, output1: str) -> None:
    # This function is RANKED: it runs as M parallel reducer instances. Use
    # this instance's own rank to process ONLY its assigned word group.
    r = faasr_rank()
    rank = r["rank"]

    remote_in = input1.format(rank=rank)
    local_in = f"shuffle_group_{rank}.json"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    with open(local_in, "r") as f:
        content = f.read()

    if not content.strip():
        faasr_log(f"reduce_word_count[{rank}]: input {folder}/{remote_in} is empty or missing.")
        raise ValueError(f"Input group {remote_in} is empty")

    group = json.loads(content)
    if not isinstance(group, dict) or "word" not in group or "counts" not in group:
        faasr_log(
            f"reduce_word_count[{rank}]: expected a JSON object with 'word' and "
            f"'counts' in {remote_in}, got {type(group).__name__}."
        )
        raise ValueError("Shuffle group is not a valid {word, counts} object")

    word = group["word"]
    counts = group["counts"]
    if not isinstance(counts, list):
        faasr_log(
            f"reduce_word_count[{rank}]: 'counts' in {remote_in} is not a list "
            f"(got {type(counts).__name__})."
        )
        raise ValueError("Shuffle group 'counts' is not a list")

    # Sum this reducer's assigned word occurrences across all map outputs (Zi).
    total = sum(counts)
    faasr_log(
        f"reduce_word_count[{rank}]: word={word!r} total={total} "
        f"from partial counts {counts}."
    )

    result = {"word": word, "count": total}
    remote_out = output1.format(rank=rank)
    local_out = f"reduce_result_{rank}.json"
    with open(local_out, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(f"reduce_word_count[{rank}]: wrote result to {folder}/{remote_out}.")

    for p in (local_in, local_out):
        if os.path.exists(p):
            os.remove(p)
