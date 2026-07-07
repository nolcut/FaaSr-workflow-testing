import os
import json

import matplotlib
matplotlib.use("Agg")  # headless, no display server available
import matplotlib.pyplot as plt


def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    # Visualization / sink stage of the MapReduce word-count benchmark.
    #
    # Fan-in: this function runs ONCE after all M=5 parallel `reduce` instances
    # finish. Each reducer wrote reduce_total_{rank}.json holding a single word
    # and its total occurrence count summed across all map partitions. Here we
    # discover every such output (without assuming a fixed count or a fixed
    # vocabulary), aggregate them into one word -> total dataset, and render a
    # bar chart to a single PNG using a headless matplotlib backend.

    # Derive the filename prefix/suffix from the input template so we can
    # discover the reduce outputs without hardcoding words or ranks.
    if "{rank}" in input1:
        in_prefix, in_suffix = input1.split("{rank}", 1)
    else:
        in_prefix, in_suffix = input1, ""

    faasr_log(
        f"visualize_outputs: discovering reduce outputs matching "
        f"'{in_prefix}*{in_suffix}' in folder '{folder}'"
    )

    # Discover all object keys in the folder (full keys incl. folder prefix).
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
            f"visualize_outputs: no reduce outputs matching "
            f"'{in_prefix}*{in_suffix}' found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(
        f"visualize_outputs: found {len(reduce_files)} reduce output(s): "
        f"{reduce_files}"
    )

    # Read each reduce output and aggregate word -> total count.
    word_totals = {}
    for base in reduce_files:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"visualize_outputs: reduce output '{base}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r") as f:
            result = json.load(f)

        if not isinstance(result, dict) or "word" not in result or "total" not in result:
            msg = (
                f"visualize_outputs: reduce output '{base}' has an unexpected "
                f"structure (expected object with 'word' and 'total'): {result!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = result["word"]
        total = result["total"]

        if not isinstance(total, int):
            msg = (
                f"visualize_outputs: reduce output '{base}' 'total' is not an "
                f"integer: {total!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        if word in word_totals:
            # Same word reported by more than one reducer: accumulate.
            word_totals[word] += total
        else:
            word_totals[word] = total

        faasr_log(
            f"visualize_outputs: read '{base}' -> word '{word}' total {total}"
        )

    # Deterministic ordering by word for a stable chart.
    words = sorted(word_totals.keys())
    totals = [word_totals[w] for w in words]

    faasr_log(
        f"visualize_outputs: aggregated {len(words)} distinct word(s): "
        f"{dict(zip(words, totals))}"
    )

    # Render the bar chart with the headless (Agg) backend.
    fig, ax = plt.subplots(figsize=(max(6, len(words) * 1.2), 6))
    positions = range(len(words))
    ax.bar(positions, totals, color="steelblue")
    ax.set_xticks(list(positions))
    ax.set_xticklabels(words, rotation=45, ha="right")
    ax.set_xlabel("Word")
    ax.set_ylabel("Total occurrence count")
    ax.set_title("MapReduce Word-Count Totals")

    for pos, total in zip(positions, totals):
        ax.text(pos, total, str(total), ha="center", va="bottom")

    fig.tight_layout()

    local_out = output1
    fig.savefig(local_out, format="png", dpi=150)
    plt.close(fig)

    if not os.path.exists(local_out) or os.path.getsize(local_out) == 0:
        msg = f"visualize_outputs: failed to render chart to '{local_out}'"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(
        f"visualize_outputs: wrote bar chart of {len(words)} word total(s) -> {output1}"
    )
