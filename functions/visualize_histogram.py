import os
import json

import matplotlib
matplotlib.use("Agg")  # headless / non-interactive backend
import matplotlib.pyplot as plt


def visualize_histogram(folder: str, input1: str, output1: str) -> None:
    # Sink node of the PDF-transcription MapReduce word count.
    #
    # The upstream reduce_step ran once and wrote one ranked JSON file per
    # distinct word (reduce_total_{rank}.json), each containing that word and its
    # final total occurrence count. Here we discover every such file in the
    # folder, aggregate the per-word totals, select the 10 words with the highest
    # counts (descending), and render a bar-chart histogram to a single PNG.

    # Derive prefix/suffix from the input template so we can discover the ranked
    # reduce outputs without assuming a fixed count or word set.
    if "{rank}" in input1:
        in_prefix, in_suffix = input1.split("{rank}", 1)
    else:
        in_prefix, in_suffix = input1, ""

    faasr_log(
        f"visualize_histogram: discovering reduce totals matching "
        f"'{in_prefix}{{rank}}{in_suffix}' in folder '{folder}'"
    )

    # Discover all object keys in the folder (full keys incl. prefix).
    keys = faasr_get_folder_list(prefix=folder)

    # Collect (rank, basename) for every reduce output whose name matches the
    # template and whose {rank} slot is a valid integer.
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
            f"visualize_histogram: no reduce totals matching "
            f"'{in_prefix}{{rank}}{in_suffix}' found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(
        f"visualize_histogram: found {len(shards)} reduce total(s): "
        f"{[b for _, b in shards]}"
    )

    # Aggregate per-word totals. Sum totals if the same word appears more than
    # once across shards (each rank is normally a distinct word, but we combine
    # defensively rather than dropping data).
    word_totals = {}
    for rank, remote_in in shards:
        local_in = remote_in
        faasr_log(
            f"visualize_histogram: fetching reduce total '{remote_in}' "
            f"from folder '{folder}'"
        )
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=remote_in)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"visualize_histogram: reduce total '{remote_in}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r") as f:
            record = json.load(f)

        if not isinstance(record, dict) or "word" not in record or "total" not in record:
            msg = (
                f"visualize_histogram: reduce total '{remote_in}' has an unexpected "
                f"structure (expected object with 'word' and 'total'): {record!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = record["word"]
        total = record["total"]

        if not isinstance(word, str):
            msg = f"visualize_histogram: reduce total '{remote_in}' 'word' is not a string: {word!r}"
            faasr_log(msg)
            raise ValueError(msg)

        if not isinstance(total, int) or isinstance(total, bool):
            msg = f"visualize_histogram: reduce total '{remote_in}' 'total' is not an integer: {total!r}"
            faasr_log(msg)
            raise ValueError(msg)

        word_totals[word] = word_totals.get(word, 0) + total

    faasr_log(f"visualize_histogram: aggregated {len(word_totals)} distinct word(s)")

    # Select the top 10 words by count (descending). Break ties by word for a
    # stable, deterministic ordering. If fewer than 10 words exist, plot all.
    ranked = sorted(word_totals.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[:10]

    words = [w for w, _ in top]
    counts = [c for _, c in top]

    faasr_log(f"visualize_histogram: top {len(top)} words: {list(zip(words, counts))}")

    # Render the histogram (bar chart) with the headless Agg backend.
    fig, ax = plt.subplots(figsize=(max(6, len(words) * 0.9), 6))
    positions = range(len(words))
    ax.bar(positions, counts, color="steelblue")
    ax.set_xticks(list(positions))
    ax.set_xticklabels(words, rotation=45, ha="right")
    ax.set_xlabel("Word")
    ax.set_ylabel("Count")
    ax.set_title(f"Top {len(words)} Most Frequent Words")
    fig.tight_layout()

    local_out = os.path.basename(output1)
    fig.savefig(local_out, format="png", dpi=150)
    plt.close(fig)

    if not os.path.exists(local_out) or os.path.getsize(local_out) == 0:
        msg = f"visualize_histogram: failed to produce histogram PNG '{local_out}'"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_histogram: wrote histogram -> {output1}")
