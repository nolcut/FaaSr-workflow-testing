import json


def reduce(folder: str, input1: str, output1: str) -> None:
    """
    Reduce function for MapReduce word count workflow.

    This function runs as 5 parallel instances. Each instance (rank 1-5) is responsible
    for counting the total occurrences of one word:
    - rank 1: cat
    - rank 2: dog
    - rank 3: bird
    - rank 4: horse
    - rank 5: pig

    Reads the shuffle shard file for this reducer's rank, which contains partial counts
    from all N=3 mappers. Sums the counts to get the total occurrence count for the word.
    """
    # Get this instance's rank (1-5)
    r = faasr_rank()
    rank = r['rank']

    # Word mapping for logging purposes
    rank_to_word = {1: "cat", 2: "dog", 3: "bird", 4: "horse", 5: "pig"}
    word = rank_to_word.get(rank, f"unknown_rank_{rank}")

    faasr_log(f"Reduce rank {rank} starting: processing word '{word}'")

    # Substitute rank into input/output filenames
    input_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    # Download the shuffle shard file for this rank
    local_input = f"shuffle_{rank}.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input_file)
    faasr_log(f"Downloaded shuffle shard: {input_file}")

    # Read partial counts from all mappers
    with open(local_input, 'r') as f:
        partial_counts = json.load(f)

    if not isinstance(partial_counts, list):
        error_msg = f"Expected a list of partial counts from {input_file}, got {type(partial_counts).__name__}"
        faasr_log(error_msg)
        raise ValueError(error_msg)

    faasr_log(f"Partial counts for '{word}' from mappers: {partial_counts}")

    # Sum the partial counts to get total count for this word
    total_count = sum(partial_counts)
    faasr_log(f"Total count for '{word}': {total_count}")

    # Write final count to output file
    local_output = f"final_count_{rank}.json"
    result = {"word": word, "count": total_count}

    with open(local_output, 'w') as f:
        json.dump(result, f)

    # Upload the final count
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)
    faasr_log(f"Reduce rank {rank} complete: wrote {output_file} with total count {total_count} for '{word}'")
