import csv
from collections import Counter


def reduce_counts(folder="MapReduce", map_prefix="map_out",
                  output_file="word_counts.csv"):
    """REDUCE step. Runs once, after all concurrent map_words ranks complete.

    Aggregates every per-shard map output into a single global word count.

    Reads  : all <folder>/<map_prefix>_*.csv objects
    Writes : <folder>/<output_file>   (columns: word,count; sorted desc)
    """
    # Discover every map output shard present in the folder.
    listing = faasr_get_folder_list(faasr_prefix=folder)

    map_objects = []
    for obj in listing:
        name = obj.split("/")[-1]
        if name.startswith(f"{map_prefix}_") and name.endswith(".csv"):
            map_objects.append(name)

    totals = Counter()
    for map_file in map_objects:
        faasr_get_file(remote_folder=folder, remote_file=map_file,
                       local_folder=".", local_file=map_file)
        with open(map_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                totals[row["word"]] += int(row["count"])

    # Write the aggregated counts sorted by frequency (descending).
    ordered = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "count"])
        for word, count in ordered:
            writer.writerow([word, count])

    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)

    faasr_log(f"reduce_counts: merged {len(map_objects)} map outputs into "
              f"{len(totals)} unique words -> {folder}/{output_file}")
