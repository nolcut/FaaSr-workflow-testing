"""FaaSr MapReduce benchmark - shuffle stage.

Generalizable: gathers every map output Yi (i < N), then FLATTENS the array
of partial-count maps into one file per distinct word.  Each per-word file
holds the list of that word's partial counts contributed by the mappers.

This flattening is what enables the desired reduce parallelism: because the
workflow primitives cannot pass the Yi array directly to ranked reducers,
shuffle materializes M independent per-word inputs so that reduce(M) can run
fully in parallel, each reducer owning exactly one word.

InvokeNext: reduce(M) -- M = number of distinct words discovered here.
"""

import json


def shuffle_flatten(folder, map_out_prefix, num_mappers, shuffle_prefix):
    """Group all mapper outputs by word into M per-word files.

    Args:
        folder:         remote S3 folder for all MapReduce artifacts.
        map_out_prefix: prefix used by map_count for its outputs.
        num_mappers:    number of map outputs to gather (N).
        shuffle_prefix: prefix for per-word output files;
                        word j (1-based, sorted) -> "<shuffle_prefix>_<j>.json".
    """
    n = int(num_mappers)

    # Flatten the Yi array: word -> list of partial counts.
    grouped = {}
    for i in range(1, n + 1):
        remote_out = f"{map_out_prefix}_{i}.json"
        local_out = f"map_out_{i}.json"
        faasr_get_file(
            local_file=local_out,
            remote_folder=folder,
            remote_file=remote_out,
        )
        with open(local_out) as f:
            partial = json.load(f)
        for word, count in partial.items():
            grouped.setdefault(word, []).append(count)

    # Deterministic word -> reducer-rank assignment (sorted vocabulary).
    words = sorted(grouped.keys())
    m = len(words)

    for j, word in enumerate(words, start=1):
        payload = {"word": word, "counts": grouped[word]}
        local_shard = f"shuffle_{j}.json"
        with open(local_shard, "w") as f:
            json.dump(payload, f)

        remote_shard = f"{shuffle_prefix}_{j}.json"
        faasr_put_file(
            local_file=local_shard,
            remote_folder=folder,
            remote_file=remote_shard,
        )
        faasr_log(
            f"shuffle_flatten: word #{j} '{word}' -> {folder}/{remote_shard} "
            f"({len(grouped[word])} partial counts)"
        )

    faasr_log(
        f"shuffle_flatten: flattened {n} map outputs into {m} per-word shards. "
        f"reduce must be invoked as reduce({m})."
    )
