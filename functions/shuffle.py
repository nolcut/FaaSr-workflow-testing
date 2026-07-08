import json
import os
from collections import defaultdict

from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_get_folder_list,
    faasr_invocation_id,
    faasr_log,
    faasr_put_file,
)


def shuffle(folder="mapreduce"):
    """
    MapReduce SHUFFLE stage (runs once, after all N map ranks complete).

    Because the workflow primitives cannot pass the array Y_i directly to the
    reducers, shuffle *flattens* the partial map outputs {Y_i | i < N}: it
    groups the per-chunk counts by word, producing, for each distinct word, a
    flat list of that word's partial counts across all maps. Each group is
    written to ``<folder>/<invocation_id>/shuffle/word_<word>.json`` and a
    manifest listing the words (in deterministic sorted order) is written so
    that M reducers can each pick up exactly one word by rank.
    """
    base_path = f"{folder}/{faasr_invocation_id()}"

    # --- Discover all map outputs Y_i ---------------------------------------
    listing = faasr_get_folder_list(faasr_prefix=f"{base_path}/map")
    y_files = sorted(
        {
            os.path.basename(p)
            for p in listing
            if os.path.basename(p).startswith("Y_")
            and os.path.basename(p).endswith(".json")
        }
    )
    faasr_log(f"shuffle: found {len(y_files)} map outputs: {y_files}")

    # --- Flatten: group partial counts by word ------------------------------
    grouped = defaultdict(list)
    for yf in y_files:
        faasr_get_file(
            local_file=yf,
            remote_folder=f"{base_path}/map",
            remote_file=yf,
        )
        with open(yf) as f:
            partial = json.load(f)
        for word, count in partial.items():
            grouped[word].append(count)

    # --- Emit one flattened group per word ----------------------------------
    words_sorted = sorted(grouped.keys())
    for word in words_sorted:
        wf = f"word_{word}.json"
        with open(wf, "w") as f:
            json.dump({"word": word, "counts": grouped[word]}, f)
        faasr_put_file(
            local_file=wf,
            remote_folder=f"{base_path}/shuffle",
            remote_file=wf,
        )

    # --- Manifest so reducers can address words by rank ---------------------
    manifest = {"words": words_sorted, "num_reducers": len(words_sorted)}
    with open("shuffle_manifest.json", "w") as f:
        json.dump(manifest, f)
    faasr_put_file(
        local_file="shuffle_manifest.json",
        remote_folder=f"{base_path}/shuffle",
        remote_file="words.json",
    )

    faasr_log(
        f"shuffle: flattened {len(y_files)} map outputs into "
        f"{len(words_sorted)} word groups (M={len(words_sorted)}): {words_sorted}"
    )
