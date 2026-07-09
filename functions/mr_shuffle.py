def mr_shuffle(folder, map_prefix, group_prefix):
    """
    SHUFFLE phase (fully generalizable) -- single action, fan-in of all N maps.

    Runs only after every ranked map invocation has finished. It reads all
    partial counts Y_i and "flattens" them: instead of one nested array of
    per-map dictionaries, it regroups the data by word so that each distinct
    word gets its own group holding the list of partial counts contributed by
    the maps. One file per word (M groups total):

        <folder>/<group_prefix><j>.json  ->  {"word": w, "partials": [c1, c2, ...]}

    Groups are indexed 1..M over the sorted set of distinct words, so reducer
    rank j deterministically handles group j. M must match the fan-out declared
    in InvokeNext (e.g. "reduce(M)").

    This flattening is what enables the reducers to run fully in parallel: the
    downstream reduce depends on the flattened per-word groups, not on the raw
    Y_i array.
    """
    import json

    # Discover all map outputs present under the folder (order-independent).
    listing = faasr_get_folder_list(faasr_prefix=folder)

    map_files = []
    for entry in listing:
        name = entry.split("/")[-1]
        if name.startswith(map_prefix) and name.endswith(".json"):
            map_files.append(name)
    map_files.sort()

    if not map_files:
        raise RuntimeError(f"mr_shuffle: no map outputs found under {folder} "
                           f"with prefix '{map_prefix}'")

    # Group partial counts by word: word -> [partial_count, ...]
    groups = {}
    for name in map_files:
        faasr_get_file(remote_folder=folder, remote_file=name,
                       local_folder=".", local_file=name)
        with open(name) as f:
            partial = json.load(f)
        for word, count in partial.items():
            groups.setdefault(word, []).append(int(count))

    # Deterministic word -> group index mapping (1-based to match ranks).
    words_sorted = sorted(groups.keys())
    for j, word in enumerate(words_sorted, start=1):
        group = {"word": word, "partials": groups[word]}
        out_name = f"{group_prefix}{j}.json"
        with open(out_name, "w") as f:
            json.dump(group, f)
        faasr_put_file(local_folder=".", local_file=out_name,
                       remote_folder=folder, remote_file=out_name)
        faasr_log(f"mr_shuffle: group {j} -> word '{word}' "
                  f"with {len(groups[word])} partials")

    faasr_log(
        f"mr_shuffle: flattened {len(map_files)} map outputs into "
        f"M={len(words_sorted)} word groups (ensure reduce fan-out == {len(words_sorted)})"
    )
