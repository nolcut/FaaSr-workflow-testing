import os
import json


def reduce_step(folder: str, input1: str, output1: str) -> None:
    # Reduce stage of the PDF-transcription MapReduce word count.
    #
    # This function runs ONCE (it is NOT a ranked instance). The upstream
    # shuffle_step discovered the vocabulary dynamically from the real PDF
    # transcription and emitted one shard per distinct word, keyed by rank
    # (shuffle_word_{rank}.json). Each shard holds a single word plus the list
    # of that word's partial counts across all map outputs.
    #
    # Here we discover every shuffle shard in the folder (the reducer count IS
    # the discovered vocabulary size, never a hardcoded M), sum each shard's
    # partial counts to yield the final total occurrences of its word, and write
    # one ranked JSON output per word (reduce_total_{rank}.json) so the
    # downstream histogram/top-10 step can consume all totals.

    # Derive the shuffle-shard filename prefix/suffix from the input template so
    # we can discover shards without assuming a fixed count or word set.
    if "{rank}" in input1:
        in_prefix, in_suffix = input1.split("{rank}", 1)
    else:
        in_prefix, in_suffix = input1, ""

    faasr_log(
        f"reduce: discovering shuffle shards matching '{in_prefix}{{rank}}{in_suffix}' "
        f"in folder '{folder}'"
    )

    # Discover all shuffle shard object keys in the folder (full keys incl. prefix).
    keys = faasr_get_folder_list(prefix=folder)

    # Collect (rank, basename) for every shard whose name matches the template
    # and whose {rank} slot is a valid integer.
    shards = []
    for key in keys:
        base = key.rsplit("/", 1)[-1]
        if not (base.startswith(in_prefix) and base.endswith(in_suffix)):
            continue
        middle = base[len(in_prefix): len(base) - len(in_suffix) if in_suffix else len(base)]
        if not middle.isdigit():
            continue
        shards.append((int(middle), base))

    # Deduplicate by rank and process in ascending rank order.
    shards = sorted(set(shards))

    if not shards:
        msg = (
            f"reduce: no shuffle shards matching '{in_prefix}{{rank}}{in_suffix}' "
            f"found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"reduce: found {len(shards)} shuffle shard(s): {[b for _, b in shards]}")

    for rank, remote_in in shards:
        local_in = remote_in
        faasr_log(f"reduce: rank {rank} fetching shuffle shard '{remote_in}' from folder '{folder}'")
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"reduce: shuffle shard '{remote_in}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r") as f:
            shard = json.load(f)

        if not isinstance(shard, dict) or "word" not in shard or "partial_counts" not in shard:
            msg = (
                f"reduce: shuffle shard '{remote_in}' has an unexpected structure "
                f"(expected object with 'word' and 'partial_counts'): {shard!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = shard["word"]
        partial_counts = shard["partial_counts"]

        if not isinstance(partial_counts, list) or not all(
            isinstance(c, int) and not isinstance(c, bool) for c in partial_counts
        ):
            msg = (
                f"reduce: shuffle shard '{remote_in}' 'partial_counts' is not a list "
                f"of integers: {partial_counts!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        total = sum(partial_counts)

        faasr_log(
            f"reduce: rank {rank} word '{word}' summed {len(partial_counts)} partial "
            f"counts {partial_counts} -> total {total}"
        )

        result = {
            "word": word,
            "total": total,
            "num_partials": len(partial_counts),
            "partial_counts": partial_counts,
        }

        remote_out = output1.replace("{rank}", str(rank))
        local_out = remote_out
        with open(local_out, "w") as f:
            json.dump(result, f)

        faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=remote_out)
        faasr_log(f"reduce: rank {rank} wrote final total for '{word}' -> {remote_out}")

    faasr_log(f"reduce: complete, wrote {len(shards)} per-word total(s)")
