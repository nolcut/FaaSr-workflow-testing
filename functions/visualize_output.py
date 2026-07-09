import json
import os

import matplotlib
matplotlib.use("Agg")  # headless, non-interactive backend (no display in container)
import matplotlib.pyplot as plt


def visualize_output(folder: str, input1: str, output1: str) -> None:
    # input1 is a rank-templated name like "word_total_{rank}.json". Derive the
    # static prefix/suffix so we can discover ALL reducer outputs at runtime
    # (do not hardcode any count or word list).
    if "{rank}" in input1:
        prefix_frag, suffix_frag = input1.split("{rank}", 1)
    else:
        prefix_frag, suffix_frag = input1, ""

    # Discover every reducer output in the folder. faasr_get_folder_list returns
    # FULL object keys including the folder prefix; match on the basename.
    all_keys = faasr_get_folder_list(prefix=folder)
    basenames = sorted(
        {
            k.rsplit("/", 1)[-1]
            for k in all_keys
            if k.rsplit("/", 1)[-1].startswith(prefix_frag)
            and k.rsplit("/", 1)[-1].endswith(suffix_frag)
        }
    )

    if not basenames:
        msg = (
            f"visualize_output: no reducer outputs matching '{prefix_frag}*{suffix_frag}' "
            f"found in folder {folder}"
        )
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_log(
        f"visualize_output: discovered {len(basenames)} reducer output(s): {basenames}"
    )

    # Assemble the word -> total-count mapping across all reducers.
    word_totals = {}
    for name in basenames:
        local_file = name
        faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=name)

        with open(local_file, "r") as f:
            data = json.load(f)

        if not isinstance(data, dict) or "word" not in data or "total" not in data:
            msg = (
                f"visualize_output: {name} is missing expected keys "
                f"('word', 'total'); got {type(data).__name__}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = data["word"]
        total = data["total"]
        # Combine defensively in case two reducers report the same word.
        word_totals[word] = word_totals.get(word, 0) + total

        if os.path.exists(local_file):
            os.remove(local_file)

    if not word_totals:
        msg = "visualize_output: no word totals assembled from reducer outputs"
        faasr_log(msg)
        raise RuntimeError(msg)

    # Order words by descending count for a readable chart.
    items = sorted(word_totals.items(), key=lambda kv: (-kv[1], kv[0]))
    words = [w for w, _ in items]
    counts = [c for _, c in items]

    faasr_log(
        f"visualize_output: rendering bar chart for {len(words)} words; "
        f"totals sum to {sum(counts)}"
    )

    # Render the bar chart, scaling width with the vocabulary size.
    fig_width = max(6.0, 0.5 * len(words))
    fig, ax = plt.subplots(figsize=(fig_width, 6.0))
    ax.bar(range(len(words)), counts, color="steelblue")
    ax.set_xticks(range(len(words)))
    ax.set_xticklabels(words, rotation=90, ha="center")
    ax.set_xlabel("Word")
    ax.set_ylabel("Total occurrence count")
    ax.set_title("MapReduce word count totals")
    fig.tight_layout()

    local_out = "word_count_chart.png"
    fig.savefig(local_out, dpi=150)
    plt.close(fig)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_output: wrote chart {output1} to {folder}")

    if os.path.exists(local_out):
        os.remove(local_out)
