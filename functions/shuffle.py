import json
import os


def shuffle(folder, M=5):
    """
    MapReduce SHUFFLE stage (single action; runs after ALL map ranks finish).

    Flattens the array of per-map partial results { Y_i | i < N } into one
    group per distinct word. Because the workflow primitives cannot pass the
    Y_i array object directly, shuffle materializes the flattened groups as
    individual S3 objects so the reduce stage can fan out over them.

    Reads : {folder}/{invocation_id}/map/map_out_*.json
    Writes: {folder}/{invocation_id}/shuffle/word_{k}.json
            -> {"word": w, "counts": [partial_count_from_each_map, ...]}
            {folder}/{invocation_id}/shuffle/manifest.json
            -> {"1": word1, "2": word2, ...}   (reducer rank -> word)

    Distinct words are sorted so the rank -> word assignment is deterministic.
    M is the configured number of reducers (should equal the number of distinct
    words); it is used only for a sanity-check log.
    """
    M = int(M)
    inv = faasr_invocation_id()
    base = f"{folder}/{inv}"

    listing = faasr_get_folder_list(faasr_prefix=f"{base}/map")
    map_files = [p for p in listing if os.path.basename(p).startswith("map_out_")
                 and p.endswith(".json")]

    # word -> flattened list of partial counts (one entry per map that saw it)
    flattened = {}
    for p in sorted(map_files):
        fname = os.path.basename(p)
        faasr_get_file(remote_folder=f"{base}/map", remote_file=fname, local_file=fname)
        with open(fname) as f:
            data = json.load(f)
        for word, count in data["counts"].items():
            flattened.setdefault(word, []).append(count)

    words = sorted(flattened.keys())

    manifest = {}
    for k, word in enumerate(words, start=1):
        manifest[str(k)] = word
        group = {"word": word, "counts": flattened[word]}
        local = f"word_{k}.json"
        with open(local, "w") as f:
            json.dump(group, f)
        faasr_put_file(
            local_file=local,
            remote_folder=f"{base}/shuffle",
            remote_file=f"word_{k}.json",
        )

    with open("manifest.json", "w") as f:
        json.dump(manifest, f)
    faasr_put_file(
        local_file="manifest.json",
        remote_folder=f"{base}/shuffle",
        remote_file="manifest.json",
    )

    faasr_log(
        f"shuffle: flattened {len(map_files)} map outputs into "
        f"{len(words)} word groups (configured M={M})"
    )
    if len(words) != M:
        faasr_log(
            f"shuffle WARNING: distinct words ({len(words)}) != configured "
            f"reducers M={M}; reducers beyond the number of words will no-op"
        )
