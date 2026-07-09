import matplotlib

matplotlib.use("Agg")  # headless backend for serverless runtime

import matplotlib.pyplot as plt
import pandas as pd


def visualize(folder="MapReduce", input_file="word_counts.csv", top_n=20):
    """
    Stage 5 of the MapReduce pipeline (visualization).

    Downloads the aggregated word-count table produced by reduce_words and
    renders a horizontal bar chart of the `top_n` most frequent words, then
    uploads the figure to `folder`/output/top_words.png.
    """
    top_n = int(top_n)

    # 1. Download the reduce output.
    faasr_log(f"visualize: downloading {folder}/reduce/{input_file}")
    faasr_get_file(
        remote_folder=f"{folder}/reduce",
        remote_file=input_file,
        local_folder=".",
        local_file="word_counts.csv",
    )

    df = pd.read_csv("word_counts.csv")
    df = df.sort_values("count", ascending=False).head(top_n)
    faasr_log(f"visualize: plotting top {len(df)} words")

    # 2. Build a horizontal bar chart (most frequent at the top).
    plt.figure(figsize=(10, 8))
    plt.barh(df["word"][::-1], df["count"][::-1], color="steelblue")
    plt.xlabel("Count")
    plt.ylabel("Word")
    plt.title(f"Top {len(df)} Most Frequent Words")
    plt.tight_layout()

    out_png = "top_words.png"
    plt.savefig(out_png, dpi=150)
    plt.close()

    # 3. Persist the figure back to S3.
    faasr_put_file(
        local_folder=".",
        local_file=out_png,
        remote_folder=f"{folder}/output",
        remote_file="top_words.png",
    )
    faasr_log(f"visualize: wrote {folder}/output/top_words.png")
