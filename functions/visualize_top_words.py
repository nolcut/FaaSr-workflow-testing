import os
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def visualize_top_words(folder: str, input1: str, output1: str) -> None:
    # Sink node of the pdf_wordcount_mapreduce workflow.
    #
    # Runs once after all M ranked `reduce_counts` instances finish. Each reducer
    # wrote a per-partition word->total mapping to reduce_total_{rank}.json. This
    # function discovers all of those outputs dynamically (the number of ranked
    # instances and the vocabulary are not known ahead of time), aggregates the
    # totals across every partition, selects the 10 most frequent words, and
    # renders a bar-chart histogram to a PNG using the headless Agg backend.

    # The input pattern carries a {rank} placeholder; derive the fixed prefix that
    # every ranked reduce output shares (e.g. "reduce_total_") and its suffix.
    prefix_marker = "{rank}"
    if prefix_marker in input1:
        name_prefix = input1.split(prefix_marker, 1)[0]
        name_suffix = input1.split(prefix_marker, 1)[1]
    else:
        name_prefix = input1
        name_suffix = ""

    faasr_log(
        f"visualize_top_words: discovering reduce outputs matching "
        f"'{name_prefix}*{name_suffix}' in folder '{folder}'"
    )

    keys = faasr_get_folder_list(prefix=folder)
    reduce_files = []
    for key in keys:
        base = key.rsplit("/", 1)[-1]
        if base.startswith(name_prefix) and base.endswith(name_suffix):
            reduce_files.append(base)
    reduce_files = sorted(set(reduce_files))

    if not reduce_files:
        msg = (
            f"visualize_top_words: no reduce output files matching "
            f"'{name_prefix}*{name_suffix}' found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(
        f"visualize_top_words: found {len(reduce_files)} reduce output(s): "
        f"{reduce_files}"
    )

    # Aggregate the word totals across every reduce partition.
    totals = {}
    for base in reduce_files:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"visualize_top_words: reduce output '{base}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r") as f:
            partition = json.load(f)

        if not isinstance(partition, dict):
            msg = (
                f"visualize_top_words: reduce output '{base}' has an unexpected "
                f"structure (expected a word->count object): {partition!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        for word, count in partition.items():
            if not isinstance(count, int):
                msg = (
                    f"visualize_top_words: word '{word}' in '{base}' has a "
                    f"non-integer count: {count!r}"
                )
                faasr_log(msg)
                raise ValueError(msg)
            totals[word] = totals.get(word, 0) + count

    if not totals:
        msg = "visualize_top_words: no word totals found across reduce outputs"
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(
        f"visualize_top_words: aggregated {len(totals)} unique word(s) "
        f"(grand total {sum(totals.values())})"
    )

    # Sort descending by count (ties broken alphabetically for determinism) and
    # take the 10 most frequent words.
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[:10]
    words = [w for w, _ in top]
    counts = [c for _, c in top]

    faasr_log(f"visualize_top_words: top words -> {top}")

    # Render the bar-chart histogram with the headless Agg backend.
    fig, ax = plt.subplots(figsize=(10, 6))
    positions = range(len(words))
    ax.bar(positions, counts, color="steelblue")
    ax.set_xticks(list(positions))
    ax.set_xticklabels(words, rotation=45, ha="right")
    ax.set_xlabel("Word")
    ax.set_ylabel("Count")
    ax.set_title("Top 10 Most Frequent Words")
    fig.tight_layout()

    local_out = output1
    fig.savefig(local_out, format="png", dpi=150)
    plt.close(fig)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_top_words: wrote histogram -> {output1}")
