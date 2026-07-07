import os
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def visualize_histogram(folder: str, input1: str, output1: str) -> None:
    # Sink stage of the MapReduce word-count benchmark.
    #
    # Fan-in: runs ONCE after all M ranked `reduce` instances finish. Each reducer
    # wrote reduce_total_{rank}.json, a JSON object holding a single word and its
    # total occurrence count aggregated across all map partitions. This function
    # discovers every such file, aggregates the word/total pairs, selects the 10
    # most frequent words (or all if fewer than 10), and renders a bar-chart
    # histogram saved as a single PNG output.

    # Derive the reduce-output filename prefix/suffix from the input template so
    # we can discover the ranked outputs without assuming a fixed count.
    if "{rank}" in input1:
        in_prefix, in_suffix = input1.split("{rank}", 1)
    else:
        in_prefix, in_suffix = input1, ""

    faasr_log(
        f"visualize_histogram: discovering reduce outputs matching "
        f"'{in_prefix}*{in_suffix}' in folder '{folder}'"
    )

    keys = faasr_get_folder_list(prefix=folder)

    reduce_files = []
    for key in keys:
        base = key.rsplit("/", 1)[-1]
        if (
            base.startswith(in_prefix)
            and base.endswith(in_suffix)
            and base != in_prefix + in_suffix
        ):
            reduce_files.append(base)

    reduce_files = sorted(set(reduce_files))

    if not reduce_files:
        msg = (
            f"visualize_histogram: no reduce outputs matching "
            f"'{in_prefix}*{in_suffix}' found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(
        f"visualize_histogram: found {len(reduce_files)} reduce output(s): "
        f"{reduce_files}"
    )

    # Aggregate word -> total across all reduce outputs.
    word_totals = {}
    for base in reduce_files:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"visualize_histogram: reduce output '{base}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r") as f:
            record = json.load(f)

        if not isinstance(record, dict) or "word" not in record or "total" not in record:
            msg = (
                f"visualize_histogram: reduce output '{base}' has an unexpected "
                f"structure (expected object with 'word' and 'total'): {record!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = record["word"]
        total = record["total"]

        if not isinstance(total, int):
            msg = (
                f"visualize_histogram: reduce output '{base}' 'total' is not an "
                f"integer: {total!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        # Sum in case a word appears in more than one reduce shard.
        word_totals[word] = word_totals.get(word, 0) + total
        faasr_log(f"visualize_histogram: read '{base}' -> word '{word}' total {total}")

    if not word_totals:
        msg = "visualize_histogram: no word/total pairs were aggregated"
        faasr_log(msg)
        raise ValueError(msg)

    # Select the top 10 words by total count (or all if fewer than 10).
    # Break ties deterministically by word for stable output.
    ranked = sorted(word_totals.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[:10]

    words = [w for (w, _c) in top]
    counts = [c for (_w, c) in top]

    faasr_log(
        f"visualize_histogram: rendering top {len(top)} words: "
        f"{list(zip(words, counts))}"
    )

    # Render the bar-chart histogram on a non-interactive backend.
    fig, ax = plt.subplots(figsize=(10, 6))
    positions = range(len(words))
    ax.bar(positions, counts, color="steelblue")
    ax.set_xticks(list(positions))
    ax.set_xticklabels(words, rotation=45, ha="right")
    ax.set_xlabel("Word")
    ax.set_ylabel("Total count")
    ax.set_title("Top 10 Most Frequent Words")
    fig.tight_layout()

    local_out = output1
    fig.savefig(local_out, format="png", dpi=150)
    plt.close(fig)

    if not os.path.exists(local_out) or os.path.getsize(local_out) == 0:
        msg = f"visualize_histogram: failed to write histogram image '{local_out}'"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(
        f"visualize_histogram: wrote histogram of {len(top)} words -> {output1}"
    )
