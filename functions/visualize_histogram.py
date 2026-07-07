import os
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def visualize_histogram(folder: str, input1: str, output1: str) -> None:
    # Sink node of the MapReduce word-count pipeline.
    #
    # Runs ONCE after all M=5 parallel `reduce` instances finish. Each reducer
    # wrote reduce_total_{rank}.json containing a single word and its final total
    # occurrence count. This function discovers every such per-rank output,
    # aggregates the word->total pairs, selects the top 10 most frequent words,
    # and renders a bar-chart histogram to a PNG using the headless Agg backend.

    # Derive the filename prefix that every reduce output shares, e.g.
    # "reduce_total_{rank}.json" -> "reduce_total_".
    marker = "{rank}"
    if marker in input1:
        name_prefix = input1.split(marker, 1)[0]
    else:
        name_prefix = input1

    faasr_log(
        f"visualize_histogram: discovering reduce outputs with basename prefix "
        f"'{name_prefix}' in folder '{folder}'"
    )

    listing = faasr_get_folder_list(prefix=folder)

    shard_basenames = []
    for key in listing:
        base = key.rsplit("/", 1)[-1]
        if base.startswith(name_prefix) and base.endswith(".json"):
            shard_basenames.append(base)

    # De-duplicate while keeping deterministic order.
    shard_basenames = sorted(set(shard_basenames))

    if not shard_basenames:
        msg = (
            f"visualize_histogram: no reduce output files matching "
            f"'{name_prefix}*.json' were found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(
        f"visualize_histogram: found {len(shard_basenames)} reduce output(s): "
        f"{shard_basenames}"
    )

    word_totals = {}
    for base in shard_basenames:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"visualize_histogram: reduce output '{base}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r") as f:
            shard = json.load(f)

        if not isinstance(shard, dict) or "word" not in shard or "total" not in shard:
            msg = (
                f"visualize_histogram: reduce output '{base}' has an unexpected "
                f"structure (expected object with 'word' and 'total'): {shard!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = shard["word"]
        total = shard["total"]

        if not isinstance(total, int):
            msg = (
                f"visualize_histogram: reduce output '{base}' 'total' is not an "
                f"integer: {total!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        # Multiple reducers should own distinct words; if a word repeats, sum it.
        word_totals[word] = word_totals.get(word, 0) + total

    if not word_totals:
        msg = "visualize_histogram: no word->total pairs were aggregated from reduce outputs"
        faasr_log(msg)
        raise ValueError(msg)

    # Sort by count descending (ties broken by word for determinism) and take top 10.
    ranked = sorted(word_totals.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[:10]

    faasr_log(f"visualize_histogram: top {len(top)} words -> {top}")

    words = [w for w, _ in top]
    counts = [c for _, c in top]

    fig, ax = plt.subplots(figsize=(max(6, len(words) * 0.8), 5))
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
        msg = f"visualize_histogram: failed to render histogram PNG '{local_out}'"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_histogram: wrote histogram -> {output1}")
