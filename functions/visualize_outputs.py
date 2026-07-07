import os
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    # Sink node of the MapReduce word-count workflow.
    #
    # Runs once after all M=5 ranked `reduce` instances finish. Each reducer wrote
    # reduce_total_{rank}.json containing a single word and its final total count
    # aggregated across all map partitions. We discover every such file in the
    # folder, collect the word/count pairs, and render a bar chart saved as PNG.

    # Derive the filename pattern from the {rank}-templated input name so we can
    # match the reducers' real output files.
    marker = "{rank}"
    if marker in input1:
        prefix_part, suffix_part = input1.split(marker, 1)
    else:
        prefix_part, suffix_part = input1, ""

    faasr_log(
        f"visualize_outputs: listing folder '{folder}' for files matching "
        f"'{prefix_part}*{suffix_part}'"
    )

    listing = faasr_get_folder_list(prefix=folder)

    matched = []
    for name in listing:
        base = name.rsplit("/", 1)[-1]
        if base.startswith(prefix_part) and base.endswith(suffix_part) and base != suffix_part:
            matched.append(base)

    # De-duplicate while keeping deterministic order.
    matched = sorted(set(matched))

    if not matched:
        msg = (
            f"visualize_outputs: no reducer output files matching "
            f"'{prefix_part}*{suffix_part}' found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"visualize_outputs: found {len(matched)} reducer outputs: {matched}")

    word_counts = {}
    for base in matched:
        local_in = base
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=base)

        if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
            msg = f"visualize_outputs: reducer output '{base}' is missing or empty"
            faasr_log(msg)
            raise FileNotFoundError(msg)

        with open(local_in, "r") as f:
            record = json.load(f)

        if not isinstance(record, dict) or "word" not in record or "total" not in record:
            msg = (
                f"visualize_outputs: reducer output '{base}' has an unexpected structure "
                f"(expected object with 'word' and 'total'): {record!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = record["word"]
        total = record["total"]

        if not isinstance(total, int):
            msg = (
                f"visualize_outputs: reducer output '{base}' 'total' is not an integer: "
                f"{total!r}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word_counts[str(word)] = word_counts.get(str(word), 0) + total
        faasr_log(f"visualize_outputs: '{base}' -> word '{word}' total {total}")

    # Order bars by descending count for a readable chart.
    ordered = sorted(word_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    words = [w for w, _ in ordered]
    counts = [c for _, c in ordered]

    faasr_log(f"visualize_outputs: rendering bar chart for {len(words)} words")

    fig_width = max(6.0, 0.6 * len(words))
    fig, ax = plt.subplots(figsize=(fig_width, 6.0))
    ax.bar(range(len(words)), counts, color="steelblue")
    ax.set_xticks(range(len(words)))
    ax.set_xticklabels(words, rotation=45, ha="right")
    ax.set_xlabel("Word")
    ax.set_ylabel("Total occurrence count")
    ax.set_title("Word occurrence counts (MapReduce word-count)")
    fig.tight_layout()

    local_out = os.path.basename(output1)
    fig.savefig(local_out, dpi=150)
    plt.close(fig)

    if not os.path.exists(local_out) or os.path.getsize(local_out) == 0:
        msg = f"visualize_outputs: failed to render chart to '{local_out}'"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_outputs: wrote bar chart -> {output1}")
