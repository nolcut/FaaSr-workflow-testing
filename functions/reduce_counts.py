import os
import json


def reduce_counts(folder: str, input1: str, output1: str) -> None:
    # Reduce stage of the MapReduce word-count workflow.
    #
    # Runs as M=5 parallel ranked instances. Each reducer reads the shuffle
    # partition assigned to its rank (shuffle_partition_{rank}.json). Unlike the
    # fixed 5-word benchmark, the vocabulary here is discovered from real PDF
    # text and is of unknown size, so each partition holds MANY words. For every
    # word in its partition the reducer sums the list of partial counts
    # contributed across all map outputs, producing that word's final total, and
    # writes the resulting word->total mapping to reduce_total_{rank}.json.

    r = faasr_rank()
    rank = r["rank"]

    remote_in = input1.replace("{rank}", str(rank))
    remote_out = output1.replace("{rank}", str(rank))

    local_in = remote_in
    faasr_log(
        f"reduce_counts: rank {rank} fetching shuffle partition '{remote_in}' "
        f"from folder '{folder}'"
    )
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"reduce_counts: shuffle partition '{remote_in}' is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    with open(local_in, "r") as f:
        shard = json.load(f)

    if not isinstance(shard, dict) or "words" not in shard:
        msg = (
            f"reduce_counts: shuffle partition '{remote_in}' has an unexpected "
            f"structure (expected object with a 'words' list): {shard!r}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    words_payload = shard["words"]
    if not isinstance(words_payload, list):
        msg = (
            f"reduce_counts: shuffle partition '{remote_in}' 'words' is not a list: "
            f"{words_payload!r}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Sum the partial counts for every word in this reducer's partition.
    totals = {}
    for entry in words_payload:
        if not isinstance(entry, dict) or "word" not in entry or "partial_counts" not in entry:
            msg = (
                f"reduce_counts: shuffle partition '{remote_in}' contains an entry "
                f"without 'word'/'partial_counts': {entry!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = entry["word"]
        partial_counts = entry["partial_counts"]

        if not isinstance(partial_counts, list) or not all(
            isinstance(c, int) for c in partial_counts
        ):
            msg = (
                f"reduce_counts: word '{word}' in partition '{remote_in}' has "
                f"'partial_counts' that is not a list of integers: {partial_counts!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        if word in totals:
            msg = (
                f"reduce_counts: word '{word}' appears more than once in partition "
                f"'{remote_in}'"
            )
            faasr_log(msg)
            raise ValueError(msg)

        totals[word] = sum(partial_counts)

    faasr_log(
        f"reduce_counts: rank {rank} reduced {len(totals)} word(s) from partition "
        f"'{remote_in}' (grand total {sum(totals.values())})"
    )

    # Final per-partition word->total mapping consumed by visualize_top_words.
    local_out = remote_out
    with open(local_out, "w") as f:
        json.dump(totals, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(
        f"reduce_counts: rank {rank} wrote {len(totals)} word total(s) -> {remote_out}"
    )
