import json
from collections import Counter


def map(folder: str, input1: str, output1: str) -> None:
    """
    Count word occurrences in the assigned text chunk.

    This function runs as N=3 parallel instances. Each instance:
    1. Gets its rank (1, 2, or 3) from faasr_rank()
    2. Reads its assigned batch file (batch_{rank}.json)
    3. Counts occurrences of each word in that chunk
    4. Outputs word counts as JSON (map_counts_{rank}.json)
    """
    # Get this instance's rank
    r = faasr_rank()
    rank = r['rank']
    max_rank = r['max_rank']

    faasr_log(f"Map instance {rank}/{max_rank} starting")

    # Substitute rank into input/output filenames
    input_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    # Download the batch file for this rank
    local_input = f"batch_{rank}.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input_file)
    faasr_log(f"Downloaded input file: {input_file}")

    # Read the word list from the batch file
    with open(local_input, 'r') as f:
        words = json.load(f)

    if not isinstance(words, list):
        error_msg = f"Expected a list of words, got {type(words).__name__}"
        faasr_log(error_msg)
        raise ValueError(error_msg)

    faasr_log(f"Read {len(words)} words from batch {rank}")

    # Count word occurrences
    word_counts = Counter(words)

    # Convert Counter to regular dict for JSON serialization
    counts_dict = dict(word_counts)

    faasr_log(f"Counted {len(counts_dict)} unique words in batch {rank}")

    # Write the counts to local file
    local_output = f"map_counts_{rank}.json"
    with open(local_output, 'w') as f:
        json.dump(counts_dict, f)

    # Upload to S3
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)
    faasr_log(f"Uploaded output file: {output_file}")

    faasr_log(f"Map instance {rank} complete - word counts: {counts_dict}")
