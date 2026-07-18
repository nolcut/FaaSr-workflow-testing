import csv
from collections import Counter


def reducer(map_folder="MapReduce/map_out", output_folder="MapReduce/reduce_out",
            output_file="word_counts.csv"):
    """REDUCE stage of the MapReduce word-count.

    Runs once, only after all concurrent mappers have completed (FaaSr fan-in
    synchronization). Aggregates every partial count file into a single global
    word-count table sorted by descending frequency.

    Reads:  {map_folder}/counts_*.csv
    Writes: {output_folder}/{output_file}
    """
    # Discover all partial-count files produced by the mappers
    listing = faasr_get_folder_list(prefix=map_folder)
    partials = [obj for obj in listing if obj.endswith(".csv")]

    totals = Counter()
    for obj in partials:
        # obj may be a full key/prefix; use only the file name locally
        remote_file = obj.split("/")[-1]
        local_file = remote_file
        faasr_get_file(
            remote_folder=map_folder,
            remote_file=remote_file,
            local_folder=".",
            local_file=local_file,
        )
        with open(local_file, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                totals[row["word"]] += int(row["count"])

    # Sort by count (desc), then word (asc) for deterministic output
    ordered = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))

    with open(output_file, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["word", "count"])
        for word, count in ordered:
            writer.writerow([word, count])

    faasr_put_file(
        local_folder=".",
        local_file=output_file,
        remote_folder=output_folder,
        remote_file=output_file,
    )

    faasr_log(
        f"reducer: aggregated {len(partials)} partial files into "
        f"{len(ordered)} unique words -> {output_folder}/{output_file}"
    )
