import os
import json


def reduce(folder: str, input1: str, output1: str) -> None:
    # Reduce stage of the MapReduce word-count benchmark.
    #
    # Runs as M=5 parallel ranked instances. Each reducer reads the shuffle shard
    # assigned to its rank (shuffle_word_{rank}.json) and sums the partial counts
    # (contributed by every map output) into a final total for each word assigned
    # to this rank, writing the per-word total(s) to reduce_total_{rank}.json.
    #
    # The upstream shuffle distributes a discovered vocabulary of arbitrary size
    # across the fixed number of reducers by a deterministic index->rank partition.
    # The vocabulary size therefore does NOT generally equal the reducer count: a
    # rank may be assigned zero words (vocabulary smaller than the reducer count),
    # exactly one word, or several words (vocabulary larger than the reducer count).
    # This reducer handles all three cases generically and does not assume a
    # one-to-one word/reducer correspondence.

    r = faasr_rank()
    rank = r["rank"]

    remote_in = input1.replace("{rank}", str(rank))
    remote_out = output1.replace("{rank}", str(rank))

    local_in = remote_in
    faasr_log(
        f"reduce: rank {rank} fetching shuffle shard '{remote_in}' from folder '{folder}'"
    )
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"reduce: shuffle shard '{remote_in}' is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    with open(local_in, "r", encoding="utf-8") as f:
        shard = json.load(f)

    if not isinstance(shard, dict):
        msg = (
            f"reduce: shuffle shard '{remote_in}' has an unexpected structure "
            f"(expected a JSON object): {shard!r}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Build the generic word -> list-of-partial-counts mapping for this rank.
    # Preferred source is the shuffle 'words' map (word -> partial counts across
    # all map outputs). Fall back to the 'assignments' list, then to the legacy
    # single-word (word/partial_counts) form, so the reducer stays compatible with
    # any shuffle output that carries the same information.
    word_partials = {}

    if isinstance(shard.get("words"), dict):
        for word, counts_list in shard["words"].items():
            word_partials[word] = counts_list
    elif isinstance(shard.get("assignments"), list):
        for entry in shard["assignments"]:
            if not isinstance(entry, dict) or "word" not in entry or "partial_counts" not in entry:
                msg = (
                    f"reduce: shuffle shard '{remote_in}' has a malformed assignment "
                    f"entry: {entry!r}"
                )
                faasr_log(msg)
                raise ValueError(msg)
            word_partials[entry["word"]] = entry["partial_counts"]
    elif "word" in shard and "partial_counts" in shard:
        word_partials[shard["word"]] = shard["partial_counts"]
    else:
        msg = (
            f"reduce: shuffle shard '{remote_in}' does not contain any recognizable "
            f"word/partial-count payload ('words', 'assignments', or "
            f"'word'+'partial_counts'): {shard!r}"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Guard: a rank may legitimately receive no assigned words when the vocabulary
    # is smaller than the reducer count. Handle gracefully — there is nothing to
    # sum, so emit no total and finish without error.
    if not word_partials:
        faasr_log(
            f"reduce: rank {rank} was assigned no words (vocabulary size "
            f"{shard.get('vocabulary_size', '?')} < reducer count); nothing to "
            f"reduce, exiting gracefully without writing an output file"
        )
        return

    # Sum the partial counts for every word assigned to this rank.
    totals = {}
    words_detail = []
    for word, partial_counts in word_partials.items():
        if not isinstance(partial_counts, list) or not all(
            isinstance(c, int) for c in partial_counts
        ):
            msg = (
                f"reduce: shuffle shard '{remote_in}' partial counts for word "
                f"{word!r} is not a list of integers: {partial_counts!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word_total = sum(partial_counts)
        totals[word] = word_total
        words_detail.append(
            {
                "word": word,
                "total": word_total,
                "num_partials": len(partial_counts),
                "partial_counts": partial_counts,
            }
        )
        faasr_log(
            f"reduce: rank {rank} word '{word}' summed {len(partial_counts)} "
            f"partial count(s) {partial_counts} -> total {word_total}"
        )

    # Deterministic order for readability/reproducibility.
    words_detail.sort(key=lambda d: (-d["total"], d["word"]))

    result = {
        "rank": rank,
        "num_words": len(totals),
        # Generalizable payload: every word assigned to this rank and its final
        # total occurrences aggregated across all map outputs.
        "totals": totals,
        "words": words_detail,
    }

    # Backward-compatible single-word convenience keys. A downstream consumer that
    # expects one (word, total) pair per reduce file reads the rank's most
    # frequent word; the full per-word breakdown remains available in 'totals'.
    representative = words_detail[0]
    result["word"] = representative["word"]
    result["total"] = representative["total"]
    result["num_partials"] = representative["num_partials"]
    result["partial_counts"] = representative["partial_counts"]

    local_out = remote_out
    with open(local_out, "w", encoding="utf-8") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
    faasr_log(
        f"reduce: rank {rank} wrote total(s) for {len(totals)} word(s) "
        f"{totals} -> {remote_out}"
    )
