import json

import matplotlib

matplotlib.use("Agg")  # headless backend for serverless execution
import matplotlib.pyplot as plt


def visualize_histogram(folder, reduce_prefix, num_reduces, top_n, output):
    """
    Stage 6 - Visualize (runs once, after ALL reduce ranks complete).

    Every reduce action's InvokeNext points here, so FaaSr's barrier ensures a
    single execution after all `num_reduces` reducers finish. It merges every
    reducer's final totals, selects the `top_n` most frequent words, and renders
    them as a bar-chart histogram saved to S3.

    Arguments:
      folder        : S3 folder for reduce inputs and the output image.
      reduce_prefix : prefix of reduce outputs (e.g. "reduce_out").
      num_reduces   : number of reduce outputs to read (e.g. 5).
      top_n         : how many top words to plot (e.g. 10).
      output        : output image file name (e.g. "histogram.png").
    """
    num_reduces = int(num_reduces)
    top_n = int(top_n)

    # Reducers partition the vocabulary by hash, so keys are disjoint; we merge
    # them into one global count table.
    totals = {}
    for r in range(1, num_reduces + 1):
        in_name = f"{reduce_prefix}_{r}.json"
        faasr_get_file(remote_folder=folder, remote_file=in_name, local_file=in_name)
        with open(in_name, "r", encoding="utf-8") as f:
            part = json.load(f)
        for word, count in part.items():
            totals[word] = totals.get(word, 0) + count

    # Rank by frequency (ties broken alphabetically) and take the top N.
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[:top_n]
    faasr_log(
        f"visualize_histogram: {len(totals)} unique words total; "
        f"top {len(top)} = {top}"
    )

    words = [w for w, _ in top]
    freqs = [c for _, c in top]

    plt.figure(figsize=(11, 6))
    plt.bar(range(len(words)), freqs, color="#4C78A8")
    plt.xticks(range(len(words)), words, rotation=45, ha="right")
    plt.xlabel("Word")
    plt.ylabel("Frequency")
    plt.title(f"Top {len(words)} Most Frequent Words")
    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()

    faasr_put_file(local_file=output, remote_folder=folder, remote_file=output)

    faasr_log(f"visualize_histogram: wrote histogram to {folder}/{output}")
