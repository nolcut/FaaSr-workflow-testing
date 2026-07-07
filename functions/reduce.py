import json
import os


def reduce(folder: str, input1: str, output1: str) -> None:
    # Fixed vocabulary (M = 5 distinct words) for the word-count benchmark.
    # Rank -> word mapping is deterministic via sorted word order, matching the
    # upstream `shuffle` step which emits one group file per sorted word index.
    WORDS = ["cat", "dog", "bird", "horse", "pig"]
    SORTED_WORDS = sorted(WORDS)  # ['bird', 'cat', 'dog', 'horse', 'pig']
    M = len(SORTED_WORDS)

    r = faasr_rank()
    rank = r["rank"]
    faasr_log(f"reduce: starting instance rank={rank} (max_rank={r.get('max_rank')})")

    if not (1 <= rank <= M):
        msg = f"reduce: rank {rank} out of range 1..{M}"
        faasr_log(msg)
        raise ValueError(msg)

    assigned_word = SORTED_WORDS[rank - 1]

    in_name = input1.format(rank=rank)
    out_name = output1.format(rank=rank)

    local_in = os.path.basename(in_name)
    faasr_log(
        f"reduce[{rank}]: fetching group file '{in_name}' for word '{assigned_word}'"
    )
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=in_name)

    with open(local_in, "r") as f:
        group = json.load(f)

    if not isinstance(group, dict):
        raise ValueError(
            f"reduce[{rank}]: expected a JSON object in {in_name}, "
            f"got {type(group).__name__}"
        )

    word = group.get("word")
    counts = group.get("counts")

    if word is None or counts is None:
        raise ValueError(
            f"reduce[{rank}]: group file {in_name} missing 'word' or 'counts': {group!r}"
        )

    if word != assigned_word:
        raise ValueError(
            f"reduce[{rank}]: group file word '{word}' does not match rank-assigned "
            f"word '{assigned_word}'"
        )

    if not isinstance(counts, list):
        raise ValueError(
            f"reduce[{rank}]: expected 'counts' to be a list in {in_name}, "
            f"got {type(counts).__name__}"
        )

    total = 0
    for c in counts:
        if not isinstance(c, (int, float)) or isinstance(c, bool):
            raise ValueError(
                f"reduce[{rank}]: non-numeric partial count {c!r} in {in_name}"
            )
        total += c

    result = {"word": word, "total": total}

    local_out = os.path.basename(out_name)
    with open(local_out, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=out_name)
    faasr_log(
        f"reduce[{rank}]: word '{word}' total={total} "
        f"(from {len(counts)} partial counts) -> {out_name}"
    )

    if os.path.exists(local_in):
        os.remove(local_in)
    if os.path.exists(local_out):
        os.remove(local_out)

    faasr_log(f"reduce[{rank}]: complete")
