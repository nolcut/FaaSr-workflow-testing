import json
import os

import matplotlib
matplotlib.use("Agg")  # headless, non-interactive backend (no display server)
import matplotlib.pyplot as plt


def visualize_output(folder: str, input1: str, output1: str) -> None:
    # Fan-in from ranked predecessor `reduce`: discover ALL per-rank final result
    # files at runtime (do not assume a fixed reducer count or hardcode words).
    prefix = input1.split("{", 1)[0]  # "final_count_"

    all_names = faasr_get_folder_list(prefix=folder)
    result_files = sorted(
        name for name in all_names
        if name.rsplit("/", 1)[-1].startswith(prefix)
        and name.rsplit("/", 1)[-1].endswith(".json")
    )

    if not result_files:
        msg = (
            f"visualize_output: found no final-count inputs under folder "
            f"'{folder}' (prefix '{prefix}')"
        )
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_log(f"[visualize] found {len(result_files)} reducer outputs: {result_files}")

    # Aggregate every per-reducer {word: total} object into one word->count map.
    word_counts = {}
    for name in result_files:
        base = name.rsplit("/", 1)[-1]
        faasr_get_file(local_file=base, remote_folder=folder, remote_file=base)
        with open(base, "r") as f:
            result = json.load(f)
        if not isinstance(result, dict):
            raise ValueError(
                f"Expected a JSON object (word->count) in {base}, "
                f"got {type(result).__name__}"
            )
        for word, count in result.items():
            word_counts[word] = word_counts.get(word, 0) + count
        try:
            os.remove(base)
        except OSError:
            pass

    if not word_counts:
        msg = "visualize_output: reducer outputs contained no word counts to plot."
        faasr_log(msg)
        raise RuntimeError(msg)

    # Stable, deterministic ordering: highest count first, then alphabetical.
    items = sorted(word_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    words = [w for w, _ in items]
    counts = [c for _, c in items]

    faasr_log(f"[visualize] plotting {len(words)} words: {dict(items)}")

    # --- Render the bar chart headlessly. ---
    fig, ax = plt.subplots(figsize=(max(6, len(words) * 0.6), 5))
    ax.bar(range(len(words)), counts, color="steelblue")
    ax.set_xticks(range(len(words)))
    ax.set_xticklabels(words, rotation=45, ha="right")
    ax.set_xlabel("Word")
    ax.set_ylabel("Total occurrence count")
    ax.set_title("MapReduce Word Count")
    for i, c in enumerate(counts):
        ax.text(i, c, str(c), ha="center", va="bottom")
    fig.tight_layout()

    local_output = "word_count_plot.png"
    fig.savefig(local_output, dpi=150)
    plt.close(fig)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"[visualize] wrote bar chart to {folder}/{output1}")

    try:
        os.remove(local_output)
    except OSError:
        pass
