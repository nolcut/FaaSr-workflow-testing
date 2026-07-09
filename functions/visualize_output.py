import json
import os

import matplotlib
matplotlib.use("Agg")  # headless backend — no display server in the container
import matplotlib.pyplot as plt


def visualize_output(folder: str, input1: str, output1: str) -> None:
    # input1 is a template like "final_count_{rank}.json". Derive the static
    # prefix/suffix so we can discover every per-reducer result file at runtime
    # without hardcoding the number of reducers.
    prefix_part = input1.split("{rank}")[0]  # "final_count_"
    suffix_part = input1.split("{rank}")[-1]  # ".json"

    # Discover the ranked final-count files in the folder (FULL object keys).
    keys = faasr_get_folder_list(prefix=f"{folder}/{prefix_part}")
    result_files = []
    for key in keys:
        base = key.rsplit("/", 1)[-1]
        if base.startswith(prefix_part) and base.endswith(suffix_part):
            result_files.append(base)
    result_files = sorted(set(result_files))

    if not result_files:
        msg = (
            f"No reducer result files matching '{prefix_part}*{suffix_part}' "
            f"found in {folder}"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"Discovered {len(result_files)} reducer result file(s): {result_files}")

    # Load each result and merge into the combined word->count mapping.
    word_counts = {}
    for base in result_files:
        local_file = base
        faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=base)
        with open(local_file, "r") as f:
            part = json.load(f)
        if not isinstance(part, dict):
            raise ValueError(
                f"Expected a JSON object (word->count) in {base}, "
                f"got {type(part).__name__}"
            )
        for word, count in part.items():
            word_counts[word] = word_counts.get(word, 0) + count
        try:
            os.remove(local_file)
        except OSError:
            pass

    if not word_counts:
        msg = f"Reducer result files in {folder} contained no word counts"
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"Aggregated {len(word_counts)} words: {word_counts}")

    # Sort by descending count (then word) for a readable chart.
    items = sorted(word_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    words = [w for w, _ in items]
    counts = [c for _, c in items]

    local_out = "word_count_chart.png"
    fig_width = max(6.0, 0.5 * len(words))
    fig, ax = plt.subplots(figsize=(fig_width, 6.0))
    ax.bar(range(len(words)), counts, color="steelblue")
    ax.set_xticks(range(len(words)))
    ax.set_xticklabels(words, rotation=45, ha="right")
    ax.set_xlabel("Word")
    ax.set_ylabel("Count")
    ax.set_title("Word Count")
    for i, c in enumerate(counts):
        ax.text(i, c, str(c), ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(local_out, dpi=150)
    plt.close(fig)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"Wrote word-count chart to {folder}/{output1}")

    try:
        os.remove(local_out)
    except OSError:
        pass
