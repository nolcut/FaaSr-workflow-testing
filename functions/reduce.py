import json


def reduce(folder: str, input1: str, output1: str) -> None:
    """
    Count the total occurrences of the assigned word across all flattened shuffle data.

    This is the reduce phase (Zi) of the MapReduce workflow. Read the assigned shard
    from the flattened shuffle output (based on this reducer's rank), which contains
    all occurrences of a specific word collected from all mappers. Sum the counts for
    that word to produce the final total count Zi.

    Rank-to-word mapping:
      Rank 1 = cat
      Rank 2 = dog
      Rank 3 = bird
      Rank 4 = horse
      Rank 5 = pig
    """
    # Get rank for this parallel instance
    r = faasr_rank()
    rank = r['rank']

    faasr_log(f"Reduce instance {rank} starting")

    # Resolve input/output filenames using rank
    input_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    # Download the shard file for this reducer
    local_input = f"temp_reduce_shard_{rank}.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input_file)

    # Read the shard data
    with open(local_input, 'r') as f:
        shard_data = json.load(f)

    word = shard_data["word"]
    partial_counts = shard_data["partial_counts"]

    faasr_log(f"Reduce instance {rank}: processing word '{word}' with {len(partial_counts)} partial counts")

    # Sum all partial counts to get the final total
    total_count = sum(partial_counts)

    faasr_log(f"Reduce instance {rank}: total count for '{word}' = {total_count}")

    # Create the final output
    result = {
        "word": word,
        "total_count": total_count
    }

    # Write to local file
    local_output = f"temp_final_count_{rank}.json"
    with open(local_output, 'w') as f:
        json.dump(result, f)

    # Upload to S3
    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)

    faasr_log(f"Reduce instance {rank}: uploaded final count to {output_file}")
    faasr_log(f"Reduce instance {rank} complete")
