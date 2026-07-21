import csv

import matplotlib

matplotlib.use("Agg")  # headless backend for the serverless runtime
import matplotlib.pyplot as plt


def visualize(reduce_folder="MapReduce/reduce_out", input_file="word_counts.csv",
              output_folder="MapReduce", output_file="word_count_plot.png",
              top_n=20):
    """Visualize the MapReduce output as a horizontal bar chart of the most
    frequent words.

    Reads:  {reduce_folder}/{input_file}
    Writes: {output_folder}/{output_file}
    """
    top_n = int(top_n)

    # Download the aggregated word counts
    faasr_get_file(
        remote_folder=reduce_folder,
        remote_file=input_file,
        local_folder=".",
        local_file="word_counts.csv",
    )

    words, counts = [], []
    with open("word_counts.csv", "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            words.append(row["word"])
            counts.append(int(row["count"]))

    # Already sorted descending by the reducer; keep the top N
    words = words[:top_n]
    counts = counts[:top_n]

    # Plot with the most frequent word at the top
    fig, ax = plt.subplots(figsize=(10, max(4, 0.4 * len(words))))
    y_pos = range(len(words))
    ax.barh(list(y_pos), counts, color="#2b8cbe")
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(words)
    ax.invert_yaxis()
    ax.set_xlabel("Count")
    ax.set_title(f"Top {len(words)} Most Frequent Words")
    fig.tight_layout()
    fig.savefig(output_file, dpi=150)
    plt.close(fig)

    # Persist the figure back to S3
    faasr_put_file(
        local_folder=".",
        local_file=output_file,
        remote_folder=output_folder,
        remote_file=output_file,
    )

    faasr_log(
        f"visualize: wrote top-{len(words)} bar chart -> {output_folder}/{output_file}"
    )
