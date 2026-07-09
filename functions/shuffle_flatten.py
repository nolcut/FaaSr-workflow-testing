"""
MapReduce - SHUFFLE stage (fully generalizable, fan-in barrier).

Because FaaSr rank successors that all point at the same action trigger that
action exactly once - only after every rank has completed - this function acts
as the barrier after the N map ranks.

It reads every partial map output Yi, then FLATTENS the array of dictionaries
into per-word groups: for each distinct word it collects the list of partial
counts contributed by the maps.  Each group is written to its own file so that
the reduce stage can process one word per rank, fully in parallel.

The distinct words are sorted deterministically and assigned indices 1..M so
that reduce rank i always operates on the same word.  A manifest records the
index -> word mapping and M (the number of reducers to launch).
"""

import json
import os


def _list_names(server_folder, prefix, suffix):
    """Return the basenames under server_folder matching prefix_*.suffix."""
    listing = faasr_get_folder_list(prefix=server_folder)
    names = []
    for entry in listing:
        base = os.path.basename(str(entry).rstrip("/"))
        if base.startswith(prefix + "_") and base.endswith(suffix):
            names.append(base)
    return sorted(set(names))


def shuffle_flatten(map_folder="MapReduce/map",
                    map_prefix="map",
                    group_folder="MapReduce/shuffle",
                    group_prefix="group",
                    manifest_file="manifest.json"):

    # ---- Collect every partial map output Yi ----------------------------
    map_files = _list_names(map_folder, map_prefix, ".json")
    faasr_log(f"[shuffle] Found {len(map_files)} map outputs: {map_files}")

    # word -> list of partial counts across all maps
    flattened = {}
    for fname in map_files:
        faasr_get_file(remote_folder=map_folder, remote_file=fname,
                       local_folder=".", local_file=fname)
        with open(fname) as fh:
            partial = json.load(fh)
        for word, cnt in partial.items():
            flattened.setdefault(word, []).append(int(cnt))

    # ---- Deterministic index -> word assignment -------------------------
    words_sorted = sorted(flattened.keys())
    M = len(words_sorted)

    manifest = {"num_words": M, "index_to_word": {}}
    for i, word in enumerate(words_sorted, start=1):
        group = {"word": word, "counts": flattened[word]}
        group_name = f"{group_prefix}_{i}.json"
        with open(group_name, "w") as fh:
            json.dump(group, fh)
        faasr_put_file(local_folder=".", local_file=group_name,
                       remote_folder=group_folder, remote_file=group_name)
        manifest["index_to_word"][str(i)] = word
        faasr_log(f"[shuffle] Group {i}: word='{word}', "
                  f"partials={flattened[word]} -> {group_folder}/{group_name}")

    with open(manifest_file, "w") as fh:
        json.dump(manifest, fh)
    faasr_put_file(local_folder=".", local_file=manifest_file,
                   remote_folder=group_folder, remote_file=manifest_file)

    faasr_log(
        f"[shuffle] Flattened {len(map_files)} map outputs into {M} word "
        f"groups. Fanning out to {M} reduce ranks."
    )
