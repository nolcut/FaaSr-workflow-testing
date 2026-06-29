import os
import json
import re
import hashlib
import tempfile


def shuffle(folder: str, input1: str, output1: str) -> None:
    """
    Reads all N partial word-count JSON files (map_result_1.json …
    map_result_N.json) produced by the map phase, merges them, and groups
    counts by word.  Distributes words to M reducers by hashing each word
    (stable MD5) modulo M.  Writes M output JSON files
    (shuffle_result_1.json … shuffle_result_M.json), each mapping the words
    assigned to that reducer to their list of partial counts across all
    mappers.

    N is discovered dynamically via faasr_get_folder_list.
    M is read from faasr_rank()["max_rank"], which the FaaSr payload sets
    to the fan-out width of the downstream `reduce` step (following the same
    convention used by `split` for its own fan-out to `map`).
    """

    # ── Determine M (number of reducers) from FaaSr payload ──────────────────
    rank_info = faasr_rank()
    m_reducers = rank_info["max_rank"]
    faasr_log(f"shuffle: will produce {m_reducers} reducer shard(s)")

    if m_reducers < 1:
        msg = f"shuffle: max_rank={m_reducers} is invalid (must be >= 1)"
        faasr_log(msg)
        raise ValueError(msg)

    # ── Discover all map_result_*.json files in the folder ───────────────────
    faasr_log(f"shuffle: discovering map result files in folder '{folder}'")
    all_files = faasr_get_folder_list(faasr_prefix=folder)

    map_pattern = re.compile(r"^map_result_\d+\.json$")
    map_files = sorted(
        f.rsplit("/", 1)[-1]
        for f in all_files
        if map_pattern.match(f.rsplit("/", 1)[-1])
    )

    n_mappers = len(map_files)
    faasr_log(f"shuffle: found {n_mappers} map result file(s): {map_files}")

    if n_mappers == 0:
        msg = "shuffle: no map_result_*.json files found in folder — cannot shuffle"
        faasr_log(msg)
        raise RuntimeError(msg)

    # ── Download every map result and merge word counts ───────────────────────
    tmp_dir = tempfile.mkdtemp(prefix="faasr_shuffle_")

    # merged_counts: word -> list of partial counts (one entry per mapper that
    # contained the word)
    merged_counts: dict[str, list] = {}

    for map_file in map_files:
        local_map = os.path.join(tmp_dir, map_file)
        faasr_log(f"shuffle: downloading '{map_file}' from folder '{folder}'")
        faasr_get_file(
    # --- CONTRACT: requires ---
    # EXISTS skipped: "map_result_{rank}.json" is a per-rank family on a non-ranked function (cannot verify a single name)
    # NON_EMPTY skipped: "map_result_{rank}.json" is a per-rank family on a non-ranked function (cannot verify a single name)
    # --- end requires ---
            local_file=local_map,
            remote_folder=folder,
            remote_file=map_file,
        )

        with open(local_map, "r", encoding="utf-8") as fh:
            partial_counts: dict = json.load(fh)

        if not isinstance(partial_counts, dict):
            msg = f"shuffle: '{map_file}' does not contain a JSON object — got {type(partial_counts)}"
            faasr_log(msg)
            raise ValueError(msg)

        for word, count in partial_counts.items():
            if word not in merged_counts:
                merged_counts[word] = []
            merged_counts[word].append(count)

        os.remove(local_map)
        faasr_log(
            f"shuffle: processed '{map_file}', running total: "
            f"{len(merged_counts)} unique words"
        )

    faasr_log(
        f"shuffle: merged {n_mappers} mapper output(s), "
        f"{len(merged_counts)} unique words total"
    )

    # ── Assign each word to a reducer via stable hash modulo M ───────────────
    # Use MD5 (not Python's hash()) for determinism across interpreter sessions.
    def word_to_reducer(w: str) -> int:
        digest = hashlib.md5(w.encode("utf-8")).digest()
        return int.from_bytes(digest, "big") % m_reducers

    # shards[r] = dict of words assigned to reducer (r+1) -> partial-count list
    shards: list[dict[str, list]] = [{} for _ in range(m_reducers)]

    for word, counts in merged_counts.items():
        idx = word_to_reducer(word)
        shards[idx][word] = counts

    for r in range(m_reducers):
        faasr_log(f"shuffle: shard {r + 1} contains {len(shards[r])} words")

    # ── Write and upload one shard file per reducer ──────────────────────────
    for r in range(1, m_reducers + 1):
        shard = shards[r - 1]
        local_shard = os.path.join(tmp_dir, f"shuffle_result_{r}.json")
        remote_shard = output1.replace("{rank}", str(r))

        with open(local_shard, "w", encoding="utf-8") as fh:
            json.dump(shard, fh, ensure_ascii=False)

        faasr_put_file(
    # --- CONTRACT: promises ---
    # EXISTS skipped: "shuffle_result_{rank}.json" is a per-rank family on a non-ranked function (cannot verify a single name)
    # NON_EMPTY skipped: "shuffle_result_{rank}.json" is a per-rank family on a non-ranked function (cannot verify a single name)
    # --- end promises ---
            local_file=local_shard,
            remote_folder=folder,
            remote_file=remote_shard,
        )
        faasr_log(
            f"shuffle: uploaded shard {r}/{m_reducers} "
            f"→ '{remote_shard}' ({len(shard)} words)"
        )
        os.remove(local_shard)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    os.rmdir(tmp_dir)
    faasr_log("shuffle: complete")