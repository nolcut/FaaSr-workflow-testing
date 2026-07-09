import math


def split_dataset(folder="MapReduce", input_file="words.txt",
                  part_prefix="part", num_parts=3):
    """Split the extracted word list into num_parts roughly-equal shards.

    Reads  : <folder>/<input_file>
    Writes : <folder>/<part_prefix>_1.txt ... <part_prefix>_<num_parts>.txt

    The shard files are consumed by the concurrent rank-based map_words action,
    where rank r reads <part_prefix>_r.txt.
    """
    num_parts = int(num_parts)

    # Download the full word list produced by extract_words.
    faasr_get_file(remote_folder=folder, remote_file=input_file,
                   local_folder=".", local_file=input_file)

    with open(input_file, "r", encoding="utf-8") as f:
        words = [w for w in f.read().splitlines() if w.strip()]

    # Compute a chunk size so the words are distributed across num_parts shards.
    chunk_size = max(1, math.ceil(len(words) / num_parts))

    for r in range(1, num_parts + 1):
        start = (r - 1) * chunk_size
        end = start + chunk_size
        shard = words[start:end]  # may be empty for trailing ranks

        part_file = f"{part_prefix}_{r}.txt"
        with open(part_file, "w", encoding="utf-8") as f:
            f.write("\n".join(shard))

        faasr_put_file(local_folder=".", local_file=part_file,
                       remote_folder=folder, remote_file=part_file)
        faasr_log(f"split_dataset: wrote {len(shard)} words to "
                  f"{folder}/{part_file}")

    faasr_log(f"split_dataset: split {len(words)} words into {num_parts} parts")
