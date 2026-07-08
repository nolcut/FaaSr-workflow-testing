"""
MapReduce - SHUFFLE stage (runs once, after all N maps complete).

Because FaaSr's workflow primitives cannot pass the array Y_i directly to
the reducers, the shuffle stage materializes/flattens it: it reads every
map output Y_i, groups the partial counts by word, and writes one input
file per word (`<reduce_prefix>_<j>.json`) so that the M reducers can each
be launched by rank and process exactly one word in parallel.

Words are sorted deterministically and assigned to ranks 1..M. The number
of distinct words discovered MUST equal `num_reducers` (M) declared in the
workflow JSON's `reduce(M)` fan-out.
"""

import json


def shuffle_words(folder="mapreduce",
                  map_prefix="map_out",
                  num_maps=3,
                  num_reducers=5,
                  reduce_prefix="reduce_in"):
    num_maps = int(num_maps)
    num_reducers = int(num_reducers)

    # ---- Collect all map outputs Y_i (discover them robustly)
    map_outputs = []
    try:
        listing = faasr_get_folder_list(faasr_prefix=folder) or []
    except Exception:
        listing = []

    remote_names = set()
    for entry in listing:
        name = entry.split("/")[-1]
        if name.startswith(map_prefix + "_") and name.endswith(".json"):
            remote_names.add(name)

    # Fall back to the expected rank-indexed names if listing was empty.
    if not remote_names:
        remote_names = {f"{map_prefix}_{i}.json" for i in range(1, num_maps + 1)}

    for name in sorted(remote_names):
        faasr_get_file(
            remote_folder=folder,
            remote_file=name,
            local_folder=".",
            local_file=name,
        )
        with open(name, "r") as f:
            map_outputs.append(json.load(f))

    faasr_log(f"[shuffle] Loaded {len(map_outputs)} map outputs (Y_i).")

    # ---- Flatten Y_i: group partial counts by word
    grouped = {}
    for partial in map_outputs:
        for word, cnt in partial.items():
            grouped.setdefault(word, []).append(int(cnt))

    words = sorted(grouped.keys())
    faasr_log(f"[shuffle] Flattened into {len(words)} word groups: {words}")

    if len(words) != num_reducers:
        faasr_log(
            f"[shuffle] WARNING: discovered {len(words)} distinct words but "
            f"reduce fan-out is {num_reducers}. Ranks without input will fail; "
            f"set reduce(M) so that M == number of distinct words."
        )

    # ---- Write one reducer-input file per word, keyed by rank j = 1..M
    for j, word in enumerate(words, start=1):
        payload = {"word": word, "partial_counts": grouped[word]}
        out_file = f"{reduce_prefix}_{j}.json"
        with open(out_file, "w") as f:
            json.dump(payload, f)

        faasr_put_file(
            local_folder=".",
            local_file=out_file,
            remote_folder=folder,
            remote_file=out_file,
        )
        faasr_log(f"[shuffle] Reducer {j} <- '{word}' "
                  f"partials={grouped[word]} -> {folder}/{out_file}")

    faasr_log(f"[shuffle] Done. Fanning out to {len(words)} reduce actions.")
