import json


def shuffle(folder: str, input1: str, input2: str, input3: str, output1: str, output2: str, output3: str, output4: str, output5: str) -> None:
    """
    Flatten word count results from N=3 parallel map functions into M=5 separate files,
    one per unique word, to enable parallel reduce processing.

    For each of the 5 words, collect all partial counts from all 3 map outputs and write
    them to a separate JSON file. Each output file contains an array of partial counts
    for that specific word from all map partitions.

    Word-to-rank mapping: rank 1=cat, rank 2=dog, rank 3=bird, rank 4=horse, rank 5=pig.
    """
    faasr_log("Starting shuffle: reorganizing map outputs by word")

    # Word-to-output mapping: rank 1=cat, rank 2=dog, rank 3=bird, rank 4=horse, rank 5=pig
    word_to_output = {
        "cat": output1,    # shuffle_1.json
        "dog": output2,    # shuffle_2.json
        "bird": output3,   # shuffle_3.json
        "horse": output4,  # shuffle_4.json
        "pig": output5,    # shuffle_5.json
    }

    # Collect partial counts for each word from all map outputs
    word_counts = {word: [] for word in word_to_output.keys()}

    # Read all 3 map count files
    input_files = [input1, input2, input3]

    for i, input_file in enumerate(input_files, start=1):
        local_file = f"map_counts_{i}.json"
        faasr_get_file(local_file=local_file, remote_folder=folder, remote_file=input_file)
        faasr_log(f"Downloaded map output: {input_file}")

        with open(local_file, 'r') as f:
            counts = json.load(f)

        if not isinstance(counts, dict):
            error_msg = f"Expected a dict of word counts from {input_file}, got {type(counts).__name__}"
            faasr_log(error_msg)
            raise ValueError(error_msg)

        # Extract the count for each word from this map output
        for word in word_counts.keys():
            count = counts.get(word, 0)
            word_counts[word].append(count)
            faasr_log(f"  {word}: {count} from map {i}")

    faasr_log("All map outputs read, writing shuffle outputs by word")

    # Write output files: one per word with array of partial counts
    for word, output_file in word_to_output.items():
        local_file = f"shuffle_{word}.json"
        partial_counts = word_counts[word]

        with open(local_file, 'w') as f:
            json.dump(partial_counts, f)

        faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Wrote {output_file} with partial counts: {partial_counts}")

    faasr_log("Shuffle complete: 5 word-specific files ready for parallel reduce")
