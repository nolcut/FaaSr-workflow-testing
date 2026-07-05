import json
from collections import Counter


def map(folder: str, input1: str, output1: str) -> None:
    """
    Count how often each word occurs in the assigned text chunk.
    Read the text batch assigned to this map instance (identified by rank).
    Parse the text and count occurrences of each word using a dictionary/counter.
    Output the word count results as a JSON file containing the word-to-count mapping.
    """
    # Get rank for this parallel instance
    r = faasr_rank()
    rank = r['rank']

    faasr_log(f"Map instance {rank} starting word count processing")

    # Resolve input/output filenames using rank
    input_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    # Download the input batch file
    local_input = f"temp_input_batch_{rank}.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input_file)

    # Read and parse the word list
    with open(local_input, 'r') as f:
        words = json.load(f)

    faasr_log(f"Map instance {rank}: loaded {len(words)} words from {input_file}")

    # Count word occurrences using Counter
    word_counts = Counter(words)

    faasr_log(f"Map instance {rank}: counted {len(word_counts)} unique words")

    # Write word counts to local file
    local_output = f"temp_output_counts_{rank}.json"
    with open(local_output, 'w') as f:
        json.dump(dict(word_counts), f)

    # Upload results to S3
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)

    faasr_log(f"Map instance {rank}: uploaded word counts to {output_file}")
    faasr_log(f"Map instance {rank} complete")
