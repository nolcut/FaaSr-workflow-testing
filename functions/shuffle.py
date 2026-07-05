import json


def shuffle(folder: str, input1: str, input2: str, input3: str, output1: str, output2: str, output3: str, output4: str, output5: str) -> None:
    """
    Flatten and reorganize the word count results from all N=3 parallel map functions
    to prepare data for M=5 parallel reducers.

    Read the partial word count outputs from each map worker.
    Reorganize the data so that each of the M=5 reducers receives all counts for one
    specific word across all map outputs.

    Output shards (by reducer rank):
      Rank 1 = cat
      Rank 2 = dog
      Rank 3 = bird
      Rank 4 = horse
      Rank 5 = pig
    """
    faasr_log("Starting shuffle: reorganizing map outputs for parallel reducers")

    # Word-to-rank mapping as specified
    word_to_rank = {
        "cat": 1,
        "dog": 2,
        "bird": 3,
        "horse": 4,
        "pig": 5
    }

    # Initialize accumulators for each word (to collect counts from all map workers)
    word_counts = {
        "cat": [],
        "dog": [],
        "bird": [],
        "horse": [],
        "pig": []
    }

    # Read all three input files from map workers
    input_files = [input1, input2, input3]

    for i, input_file in enumerate(input_files, start=1):
        local_input = f"temp_shuffle_input_{i}.json"
        faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input_file)

        with open(local_input, 'r') as f:
            counts = json.load(f)

        faasr_log(f"Read {input_file}: {len(counts)} words with counts")

        # Collect the count for each word from this map worker
        for word, count in counts.items():
            if word in word_counts:
                word_counts[word].append(count)
            else:
                faasr_log(f"Warning: unexpected word '{word}' in {input_file}")

    faasr_log(f"Collected counts from all {len(input_files)} map workers")

    # Create output shards - one per reducer rank, containing all partial counts for that word
    # Output mapping: output1=cat (rank 1), output2=dog (rank 2), output3=bird (rank 3),
    #                 output4=horse (rank 4), output5=pig (rank 5)
    output_mapping = {
        1: (output1, "cat"),
        2: (output2, "dog"),
        3: (output3, "bird"),
        4: (output4, "horse"),
        5: (output5, "pig")
    }

    for rank in range(1, 6):
        output_file, word = output_mapping[rank]
        counts_list = word_counts[word]

        # Shard contains all partial counts for this word from all map workers
        shard_data = {
            "word": word,
            "partial_counts": counts_list
        }

        local_output = f"temp_shard_{rank}.json"
        with open(local_output, 'w') as f:
            json.dump(shard_data, f)

        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Uploaded {output_file} for word '{word}' with {len(counts_list)} partial counts: {counts_list}")

    faasr_log("Shuffle complete: 5 shards ready for parallel reduce processing")
