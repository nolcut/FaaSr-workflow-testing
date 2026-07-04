import json
import tempfile
import os


def reduce(folder: str, input1: str, output1: str) -> None:
    """
    Count the total occurrences of the assigned word across all mapper outputs.
    This is a ranked function (M=5 reducers, one per unique word).
    Each reducer instance reads its assigned shuffle shard containing word counts
    from all mappers for its specific word, sums the counts to compute the final
    total occurrence count for that word, and writes the result to an output file.

    The reducer determines which word it handles based on its rank (1-indexed),
    mapping to the word list [cat, dog, bird, horse, pig].
    """
    # Get rank for this instance
    r = faasr_rank()
    rank = r['rank']

    # Map rank to word
    words = ["cat", "dog", "bird", "horse", "pig"]
    word = words[rank - 1]  # rank is 1-indexed

    faasr_log(f"Reduce rank {rank}: processing word '{word}'")

    # Substitute rank into input/output filenames
    input_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    # Download the shuffle shard for this rank
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        faasr_get_file(local_file=tmp_path, remote_folder=folder, remote_file=input_file)

        # Read the JSON content - a list of counts from all mappers
        with open(tmp_path, 'r') as f:
            content = f.read()

        if not content.strip():
            faasr_log(f"ERROR: Input file {input_file} is empty or could not be read")
            raise ValueError(f"Input file {input_file} is empty or missing")

        counts_list = json.loads(content)
        faasr_log(f"Read counts from {input_file}: {counts_list}")

        # Sum all counts to get the final total for this word
        total_count = sum(counts_list)
        faasr_log(f"Total count for word '{word}': {total_count}")

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Write the final count to output
    result = {
        "word": word,
        "total_count": total_count
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        json.dump(result, tmp)
        tmp_path = tmp.name

    try:
        faasr_put_file(local_file=tmp_path, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Uploaded final count for '{word}' ({total_count}) to {output_file}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    faasr_log(f"Reduce rank {rank} completed successfully")
