import json


def reduce_counts(folder, shuffle_prefix, output_prefix):
    """
    Stage 5 - Reduce (runs concurrently, once per rank).

    Invoked as a ranked action (e.g. "reduce(5)"): FaaSr runs `max_rank`
    concurrent copies, each handling one shuffle bucket `<shuffle_prefix>_<rank>.json`.
    Each copy sums the list of partial counts per word into a final total.

    Emits: <output_prefix>_<rank>.json = {"word": total, ...}

    Arguments:
      folder         : S3 folder for shuffle inputs and reduce outputs.
      shuffle_prefix : prefix of shuffle outputs (e.g. "shuffle").
      output_prefix  : prefix for reduced totals (e.g. "reduce_out").
    """
    rank_info = faasr_rank()
    my_rank = int(rank_info["rank"])
    max_rank = int(rank_info["max_rank"])

    in_name = f"{shuffle_prefix}_{my_rank}.json"
    faasr_get_file(remote_folder=folder, remote_file=in_name, local_file=in_name)

    with open(in_name, "r", encoding="utf-8") as f:
        bucket = json.load(f)

    # Sum the partial counts emitted by the mappers for each word.
    totals = {word: sum(partials) for word, partials in bucket.items()}

    out_name = f"{output_prefix}_{my_rank}.json"
    with open(out_name, "w", encoding="utf-8") as f:
        json.dump(totals, f)

    faasr_put_file(local_file=out_name, remote_folder=folder, remote_file=out_name)

    faasr_log(
        f"reduce_counts: rank {my_rank}/{max_rank} reduced {len(totals)} words "
        f"-> {folder}/{out_name}"
    )
