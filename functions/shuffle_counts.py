import json
import hashlib


def _reducer_for(word, num_reduces):
    """Deterministically map a word to a reducer bucket (0..num_reduces-1).

    Python's builtin hash() is salted per process, so we use md5 to guarantee
    that the SAME word is always routed to the SAME reducer across every
    invocation and every machine.
    """
    digest = hashlib.md5(word.encode("utf-8")).hexdigest()
    return int(digest, 16) % num_reduces


def shuffle_counts(folder, map_prefix, num_maps, shuffle_prefix, num_reduces):
    """
    Stage 4 - Shuffle (runs once, after ALL map ranks complete).

    Because every map action's InvokeNext points here, FaaSr's barrier ensures
    this runs a single time only after all `num_maps` map tasks have finished.

    It reads every map partial-count file, then partitions the (word, count)
    pairs across `num_reduces` reducer buckets by hashing each word. All counts
    for a given word land in the same bucket, so a reducer can sum them safely.
    The vocabulary size (total word count) need not be known in advance.

    Emits: <shuffle_prefix>_<r>.json for r in 1..num_reduces
           each = {"word": [c1, c2, ...], ...}  (partial counts to be summed)

    Arguments:
      folder         : S3 folder for map inputs and shuffle outputs.
      map_prefix     : prefix of map outputs (e.g. "map_out").
      num_maps       : number of map outputs to read (e.g. 3).
      shuffle_prefix : prefix for shuffle outputs (e.g. "shuffle").
      num_reduces    : number of reducer buckets to create (e.g. 5).
    """
    num_maps = int(num_maps)
    num_reduces = int(num_reduces)

    # One bucket per reducer; bucket maps word -> list of partial counts.
    buckets = [dict() for _ in range(num_reduces)]

    for m in range(1, num_maps + 1):
        map_name = f"{map_prefix}_{m}.json"
        faasr_get_file(remote_folder=folder, remote_file=map_name, local_file=map_name)
        with open(map_name, "r", encoding="utf-8") as f:
            partial = json.load(f)

        for word, count in partial.items():
            b = _reducer_for(word, num_reduces)
            buckets[b].setdefault(word, []).append(count)

    for r in range(num_reduces):
        out_name = f"{shuffle_prefix}_{r + 1}.json"
        with open(out_name, "w", encoding="utf-8") as f:
            json.dump(buckets[r], f)
        faasr_put_file(local_file=out_name, remote_folder=folder, remote_file=out_name)
        faasr_log(
            f"shuffle_counts: bucket {r + 1}/{num_reduces} -> "
            f"{folder}/{out_name} ({len(buckets[r])} unique words)"
        )
