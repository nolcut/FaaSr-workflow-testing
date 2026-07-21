"""
MapReduce - COLLECT stage (fully generalizable, fan-in barrier).

Runs once after all M reduce ranks complete (rank fan-in barrier). It gathers
every Zi and assembles the final word-count result, which is written to the
output folder and echoed to the log.
"""

import json
import os


def _list_names(server_folder, prefix, suffix):
    listing = faasr_get_folder_list(prefix=server_folder)
    names = []
    for entry in listing:
        base = os.path.basename(str(entry).rstrip("/"))
        if base.startswith(prefix + "_") and base.endswith(suffix):
            names.append(base)
    return sorted(set(names))


def collect_results(reduce_folder="MapReduce/reduce",
                    reduce_prefix="reduce",
                    output_folder="MapReduce/output",
                    result_file="result.json"):

    reduce_files = _list_names(reduce_folder, reduce_prefix, ".json")
    faasr_log(f"[collect] Found {len(reduce_files)} reduce outputs: "
              f"{reduce_files}")

    totals = {}
    for fname in reduce_files:
        faasr_get_file(remote_folder=reduce_folder, remote_file=fname,
                       local_folder=".", local_file=fname)
        with open(fname) as fh:
            zi = json.load(fh)
        totals[zi["word"]] = int(zi["count"])

    final = {
        "word_counts": dict(sorted(totals.items())),
        "num_words": len(totals),
        "total_occurrences": sum(totals.values()),
    }

    with open(result_file, "w") as fh:
        json.dump(final, fh, indent=2)
    faasr_put_file(local_folder=".", local_file=result_file,
                   remote_folder=output_folder, remote_file=result_file)

    faasr_log(
        f"[collect] Final word counts: {final['word_counts']} "
        f"(total={final['total_occurrences']} over {final['num_words']} words) "
        f"-> {output_folder}/{result_file}."
    )
