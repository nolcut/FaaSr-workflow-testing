import json
import os

import matplotlib

# Use a non-interactive/headless backend: the runtime has no display server.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    """Collect the per-reducer word/total JSON files and render a bar chart.

    Fan-in sink for the MapReduce word-count workflow. Reads every rank-numbered
    ``word_total_{rank}.json`` file produced by the parallel reducers, extracts
    the (word, total) pair from each, and writes a single labeled PNG bar chart.
    """

    # The rank-numbered input pattern, e.g. "word_total_{rank}.json".
    # Derive the fixed prefix/suffix so we can recognize the reducer outputs
    # among all keys in the folder.
    pattern = input1
    marker = "{rank}"
    if marker in pattern:
        prefix_part, suffix_part = pattern.split(marker, 1)
    else:
        # No template marker: treat the whole name as the recognizable stem.
        prefix_part, suffix_part = pattern, ""

    base_prefix = prefix_part.rsplit("/", 1)[-1]
    base_suffix = suffix_part

    faasr_log(
        f"visualize_outputs: discovering reducer outputs in folder '{folder}' "
        f"matching '{base_prefix}<rank>{base_suffix}'"
    )

    # Discover the actual reducer output keys (do not assume a fixed count).
    keys = faasr_get_folder_list(prefix=folder)

    matched = []
    for key in keys:
        name = key.rsplit("/", 1)[-1]
        if name.startswith(base_prefix) and name.endswith(base_suffix):
            middle = name[len(base_prefix): len(name) - len(base_suffix)] if base_suffix else name[len(base_prefix):]
            if base_prefix and middle.isdigit():
                matched.append((int(middle), name))
            elif base_prefix:
                # Recognized stem but non-numeric middle: still include it.
                matched.append((None, name))

    if not matched:
        msg = (
            f"visualize_outputs: no reducer output files matching "
            f"'{base_prefix}<rank>{base_suffix}' found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    # Sort by rank so the bars appear in reducer order.
    matched.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0, t[1]))

    words = []
    totals = []
    for rank, name in matched:
        local_in = name
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=name)

        try:
            with open(local_in, "r") as f:
                record = json.load(f)
        finally:
            if os.path.exists(local_in):
                os.remove(local_in)

        if not isinstance(record, dict):
            msg = (
                f"visualize_outputs: expected a JSON object in '{name}', "
                f"got {type(record).__name__}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = record.get("word")
        # Reducer writes {"word": ..., "count": ...}; accept "total" as a
        # synonym for robustness against upstream naming.
        total = record.get("count", record.get("total"))

        if word is None or total is None:
            msg = (
                f"visualize_outputs: '{name}' missing required 'word'/'count' "
                f"fields (got keys {sorted(record.keys())})"
            )
            faasr_log(msg)
            raise ValueError(msg)

        if isinstance(total, bool) or not isinstance(total, (int, float)):
            msg = f"visualize_outputs: non-numeric count {total!r} in '{name}'"
            faasr_log(msg)
            raise ValueError(msg)

        words.append(str(word))
        totals.append(total)
        faasr_log(f"visualize_outputs: {name} -> word='{word}' total={total}")

    faasr_log(
        f"visualize_outputs: rendering bar chart for {len(words)} words: {words}"
    )

    # Build the bar chart.
    fig, ax = plt.subplots(figsize=(max(6, len(words) * 1.2), 5))
    positions = range(len(words))
    bars = ax.bar(positions, totals, color="steelblue", edgecolor="black")

    ax.set_xticks(list(positions))
    ax.set_xticklabels(words, rotation=45, ha="right")
    ax.set_xlabel("Word")
    ax.set_ylabel("Total occurrence count")
    ax.set_title("Word Occurrence Totals (MapReduce)")

    # Annotate each bar with its value for readability.
    for rect, value in zip(bars, totals):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            rect.get_height(),
            str(int(value)) if float(value).is_integer() else str(value),
            ha="center",
            va="bottom",
        )

    ax.margins(y=0.15)
    fig.tight_layout()

    local_out = output1.rsplit("/", 1)[-1]
    fig.savefig(local_out, dpi=150, format="png")
    plt.close(fig)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_outputs: wrote chart -> {output1}")

    if os.path.exists(local_out):
        os.remove(local_out)
