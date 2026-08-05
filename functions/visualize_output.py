import os
import json

import matplotlib
matplotlib.use("Agg")  # headless, non-interactive backend
import matplotlib.pyplot as plt


def visualize_output(folder: str, input1: str, output1: str) -> None:
    # Derive the reducer-output naming pattern from input1
    # (e.g. "reduce_result_{rank}.json" -> prefix "reduce_result_", suffix ".json").
    if "{rank}" in input1:
        prefix, suffix = input1.split("{rank}", 1)
    else:
        prefix, suffix = "", input1

    # Discover ALL per-rank reducer outputs in the folder (fan-in from the
    # ranked reduce_word_count predecessor). Do not assume a fixed count.
    keys = faasr_get_folder_list(prefix=folder)
    basenames = sorted({k.rsplit("/", 1)[-1] for k in keys})
    result_files = [
        n for n in basenames if n.startswith(prefix) and n.endswith(suffix)
    ]

    if not result_files:
        faasr_log(
            f"visualize_output: no reducer output files matching "
            f"'{prefix}*{suffix}' found in folder {folder}."
        )
        raise ValueError("No reducer result files found to visualize")

    faasr_log(
        f"visualize_output: found {len(result_files)} reducer output files: "
        f"{result_files}."
    )

    # Collect word/count pairs from every reducer result file.
    pairs = {}
    for name in result_files:
        local_in = name
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=name)
        with open(local_in, "r") as f:
            content = f.read()
        if not content.strip():
            faasr_log(f"visualize_output: reducer output {name} is empty or missing.")
            raise ValueError(f"Reducer output {name} is empty")
        result = json.loads(content)
        if not isinstance(result, dict) or "word" not in result or "count" not in result:
            faasr_log(
                f"visualize_output: expected a JSON object with 'word' and "
                f"'count' in {name}, got {type(result).__name__}."
            )
            raise ValueError(f"Reducer output {name} is not a valid {{word, count}} object")
        pairs[result["word"]] = result["count"]
        if os.path.exists(local_in):
            os.remove(local_in)

    # Sort words for consistent, deterministic ordering.
    words = sorted(pairs.keys())
    counts = [pairs[w] for w in words]
    faasr_log(
        f"visualize_output: rendering bar chart for {len(words)} words: "
        + ", ".join(f"{w}={c}" for w, c in zip(words, counts))
        + "."
    )

    # Render the bar chart.
    fig, ax = plt.subplots(figsize=(max(6, len(words) * 1.2), 5))
    ax.bar(words, counts, color="steelblue")
    ax.set_xlabel("Word")
    ax.set_ylabel("Total count")
    ax.set_title("MapReduce Word Count — Total Occurrences per Word")
    fig.tight_layout()

    local_out = "word_count_chart.png"
    fig.savefig(local_out, dpi=100)
    plt.close(fig)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_output: wrote chart to {folder}/{output1}.")

    if os.path.exists(local_out):
        os.remove(local_out)
