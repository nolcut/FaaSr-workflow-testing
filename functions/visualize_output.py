import json
import os
import re

import matplotlib
matplotlib.use("Agg")  # headless backend: the runtime has no display
import matplotlib.pyplot as plt


def visualize_output(folder: str, input1: str, output1: str) -> None:
    # Discover the per-reducer final result files at runtime (do NOT hardcode the
    # reducer count or vocabulary). input1 is a template like "final_count_{rank}.json";
    # build a matcher from it and pick out every matching object in the folder.
    if "{rank}" not in input1:
        raise ValueError(f"Expected a '{{rank}}' placeholder in input pattern, got {input1!r}")
    pattern = re.compile("^" + re.escape(input1).replace(re.escape("{rank}"), r"(\d+)") + "$")

    keys = faasr_get_folder_list(prefix=folder)
    matches = []  # (rank, basename)
    for key in keys:
        base = key.rsplit("/", 1)[-1]
        m = pattern.match(base)
        if m:
            matches.append((int(m.group(1)), base))
    matches.sort()

    if not matches:
        msg = f"No reducer output files matching '{input1}' found in {folder}"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_log(f"Found {len(matches)} reducer output file(s): {[b for _, b in matches]}")

    # Aggregate (word, total count) pairs across all reducer outputs.
    totals = {}
    for rank, base in matches:
        local_file = f"final_count_{rank}.json"
        faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=base)
        with open(local_file, "r") as f:
            result = json.load(f)
        if not isinstance(result, dict):
            raise ValueError(
                f"Expected a JSON object (word->count) in {base}, got {type(result).__name__}"
            )
        for word, count in result.items():
            totals[word] = totals.get(word, 0) + count
        try:
            os.remove(local_file)
        except OSError:
            pass

    if not totals:
        msg = "No (word, count) pairs found in reducer outputs"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_log(f"Aggregated word counts: {totals}")

    # Render a bar chart of each word's total occurrence count, ordered by count.
    items = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    words = [w for w, _ in items]
    counts = [c for _, c in items]

    fig, ax = plt.subplots(figsize=(max(6, len(words) * 0.6), 5))
    ax.bar(words, counts, color="steelblue")
    ax.set_xlabel("Word")
    ax.set_ylabel("Count")
    ax.set_title("Word Count")
    for i, c in enumerate(counts):
        ax.text(i, c, str(c), ha="center", va="bottom")
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()

    local_output = "word_count_chart.png"
    fig.savefig(local_output, dpi=150)
    plt.close(fig)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"Wrote word count chart to {folder}/{output1}")

    try:
        os.remove(local_output)
    except OSError:
        pass
