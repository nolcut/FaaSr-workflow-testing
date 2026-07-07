import json
import os

import matplotlib

# Force a non-interactive, headless backend BEFORE importing pyplot so the
# function works in a display-less container.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def visualize_outputs(folder: str, input1: str, output1: str) -> None:
    """Fan-in visualizer for the MapReduce word-count workflow.

    Reads every per-word aggregated total file produced by the ranked `reduce`
    instances (word_total_1.json .. word_total_5.json), each a JSON object of
    the form {"word": <str>, "total": <number>}, and renders a bar chart of the
    total occurrence count per word to a single PNG output (word_counts.png).
    """
    faasr_log(f"visualize_outputs: discovering reducer outputs in folder '{folder}'")

    # Derive the fixed part of the ranked input filename (strip the {rank}
    # placeholder) so we can identify the reducer outputs among the folder keys.
    # e.g. "word_total_{rank}.json" -> prefix "word_total_", suffix ".json"
    if "{rank}" in input1:
        prefix_frag, suffix_frag = input1.split("{rank}", 1)
    else:
        prefix_frag, suffix_frag = input1, ""

    all_keys = faasr_get_folder_list(prefix=folder)
    faasr_log(f"visualize_outputs: folder listing returned {len(all_keys)} keys")

    # Keep only the reducer total files, matching on basename.
    matched = []
    for key in all_keys:
        base = key.rsplit("/", 1)[-1]
        if base.startswith(prefix_frag) and base.endswith(suffix_frag):
            matched.append(base)

    # Deduplicate and order deterministically.
    matched = sorted(set(matched))

    if not matched:
        msg = (
            f"visualize_outputs: no reducer output files matching "
            f"'{input1}' found in folder '{folder}'"
        )
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"visualize_outputs: found {len(matched)} reducer output files: {matched}")

    pairs = []  # list of (word, total)
    for base in matched:
        local_in = os.path.basename(base)
        faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=local_in)

        with open(local_in, "r") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            msg = (
                f"visualize_outputs: expected a JSON object in {base}, "
                f"got {type(data).__name__}"
            )
            faasr_log(msg)
            raise ValueError(msg)

        word = data.get("word")
        total = data.get("total")

        if word is None or total is None:
            msg = f"visualize_outputs: file {base} missing 'word' or 'total': {data!r}"
            faasr_log(msg)
            raise ValueError(msg)

        if not isinstance(total, (int, float)) or isinstance(total, bool):
            msg = f"visualize_outputs: non-numeric total {total!r} in {base}"
            faasr_log(msg)
            raise ValueError(msg)

        pairs.append((str(word), total))
        faasr_log(f"visualize_outputs: {base} -> word='{word}' total={total}")

        if os.path.exists(local_in):
            os.remove(local_in)

    # Sort words for a stable, readable chart ordering.
    pairs.sort(key=lambda p: p[0])
    words = [p[0] for p in pairs]
    totals = [p[1] for p in pairs]

    faasr_log(
        f"visualize_outputs: rendering bar chart for {len(words)} words: "
        + ", ".join(f"{w}={t}" for w, t in pairs)
    )

    local_out = os.path.basename(output1)

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(words, totals, color="#4C72B0")
    ax.set_xlabel("Word")
    ax.set_ylabel("Total occurrence count")
    ax.set_title("Word occurrence counts (MapReduce word-count)")
    ax.bar_label(bars)
    ax.margins(y=0.1)
    fig.tight_layout()
    fig.savefig(local_out, dpi=150)
    plt.close(fig)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"visualize_outputs: wrote bar chart -> {output1}")

    if os.path.exists(local_out):
        os.remove(local_out)

    faasr_log("visualize_outputs: complete")
