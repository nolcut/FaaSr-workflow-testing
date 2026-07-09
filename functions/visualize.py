import csv

import matplotlib
matplotlib.use("Agg")  # headless backend for a FaaS runtime (no display).
import matplotlib.pyplot as plt


def visualize(folder="MapReduce", input_file="word_counts.csv",
              output_file="word_counts.png", top_n=20):
    """Visualize the reduced word counts as a bar chart of the top-N words.

    Reads  : <folder>/<input_file>
    Writes : <folder>/<output_file>   (PNG bar chart)
    """
    top_n = int(top_n)

    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file=input_file)

    words, counts = [], []
    with open(input_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            words.append(row["word"])
            counts.append(int(row["count"]))

    # reduce_counts already writes rows sorted by descending frequency; take top-N.
    words = words[:top_n]
    counts = counts[:top_n]

    plt.figure(figsize=(12, 6))
    plt.bar(range(len(words)), counts, color="steelblue")
    plt.xticks(range(len(words)), words, rotation=45, ha="right")
    plt.xlabel("Word")
    plt.ylabel("Count")
    plt.title(f"Top {len(words)} Words")
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()

    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)

    faasr_log(f"visualize: plotted top {len(words)} words -> "
              f"{folder}/{output_file}")
