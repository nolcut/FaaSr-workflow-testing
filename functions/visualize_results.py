import json
import os
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


TOP_N = 20  # number of words shown in the bar chart


def visualize_results(folder: str, input1: str, input2: str, output1: str) -> None:
    # ── 1. Download manifest (used only for logging context) ─────────────────
    local_manifest = tempfile.mktemp(suffix=".json")
    faasr_log(f"Downloading manifest '{input2}' from folder '{folder}'")
    faasr_get_file(local_file=local_manifest, remote_folder=folder, remote_file=input2)
    with open(local_manifest, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    os.unlink(local_manifest)
    faasr_log(f"Manifest: {manifest.get('num_batches')} map batch(es)")

    # ── 2. Discover all reduce_result_*.json files via folder listing ─────────
    faasr_log(f"Listing files in folder '{folder}' to find reduce result files")
    all_keys = faasr_get_folder_list(prefix=folder)
    reduce_files = sorted(
        k.rsplit("/", 1)[-1]
        for k in all_keys
        if k.rsplit("/", 1)[-1].startswith("reduce_result_")
        and k.rsplit("/", 1)[-1].endswith(".json")
    )

    if not reduce_files:
        msg = (
            f"No reduce_result_*.json files found in folder '{folder}' — "
            "ensure all reduce instances have completed"
        )
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"Found {len(reduce_files)} reduce result file(s): {reduce_files}")

    # ── 3. Download and merge all reducer outputs ─────────────────────────────
    merged: dict = {}
    for rf in reduce_files:
        local_rf = tempfile.mktemp(suffix=".json")
        faasr_log(f"Downloading '{rf}' from folder '{folder}'")
        faasr_get_file(local_file=local_rf, remote_folder=folder, remote_file=rf)
        with open(local_rf, "r", encoding="utf-8") as fh:
            counts = json.load(fh)
        os.unlink(local_rf)
        for word, count in counts.items():
            merged[word] = merged.get(word, 0) + count

    faasr_log(f"Merged {len(merged)} unique word(s) across {len(reduce_files)} shard(s)")

    if not merged:
        msg = "All reduce result files are empty — no words to visualize"
        faasr_log(msg)
        raise ValueError(msg)

    # ── 4. Select top-N words ─────────────────────────────────────────────────
    top_words = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:TOP_N]
    labels = [w for w, _ in top_words]
    values = [c for _, c in top_words]
    faasr_log(f"Top word: '{labels[0]}' ({values[0]} occurrences); plotting top {len(labels)}")

    # ── 5. Generate bar chart ─────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(range(len(labels)), values, color="steelblue")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10)
    ax.set_xlabel("Word")
    ax.set_ylabel("Count")
    ax.set_title(f"Top {len(labels)} Most Frequent Words")
    ax.yaxis.get_major_locator().set_params(integer=True)
    fig.tight_layout()

    local_chart = tempfile.mktemp(suffix=".png")
    fig.savefig(local_chart, dpi=150)
    plt.close(fig)

    # ── 6. Upload chart to S3 ─────────────────────────────────────────────────
    faasr_log(f"Uploading chart '{output1}' to folder '{folder}'")
    faasr_put_file(local_file=local_chart, remote_folder=folder, remote_file=output1)
    os.unlink(local_chart)

    faasr_log("visualize_results complete")
