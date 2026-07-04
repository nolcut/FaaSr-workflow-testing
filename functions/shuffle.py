import json
import tempfile
import os


def shuffle(folder: str, input1: str, input2: str, input3: str, output1: str, output2: str, output3: str, output4: str, output5: str) -> None:
    """
    Flatten and reorganize the word count results from all N=3 mappers to enable M=5 parallel reducers.
    Read the partial word count JSON files from each mapper (containing counts for words: cat, dog, bird, horse, pig).
    Reorganize the data so that each of the M=5 reducers receives all counts for its assigned word across all mappers.
    Output M=5 separate JSON files, one per word, where each file contains a list of counts from all mappers for that specific word.
    """
    faasr_log("Starting shuffle: reorganizing N=3 mapper outputs for M=5 reducers")

    # The 5 words in order corresponding to the 5 outputs
    words = ["cat", "dog", "bird", "horse", "pig"]
    outputs = [output1, output2, output3, output4, output5]

    # Discover all word count files from mappers using faasr_get_folder_list
    all_files = faasr_get_folder_list(prefix=f"{folder}/word_counts_")
    faasr_log(f"Discovered mapper output files: {all_files}")

    # If no files found with the prefix, try the exact input filenames
    input_files = [input1, input2, input3]
    if not all_files:
        all_files = input_files
        faasr_log(f"Using explicit input filenames: {all_files}")

    # Collect word counts from all mappers
    # Structure: {word: [count_from_mapper1, count_from_mapper2, ...]}
    word_counts_all = {word: [] for word in words}

    for input_file in all_files:
        # Download the mapper output to a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            faasr_get_file(local_file=tmp_path, remote_folder=folder, remote_file=input_file)

            # Read the JSON content
            with open(tmp_path, 'r') as f:
                content = f.read()

            if not content.strip():
                faasr_log(f"ERROR: Input file {input_file} is empty or could not be read")
                raise ValueError(f"Input file {input_file} is empty or missing")

            mapper_counts = json.loads(content)
            faasr_log(f"Read counts from {input_file}: {mapper_counts}")

            # Collect the count for each word from this mapper
            for word in words:
                count = mapper_counts.get(word, 0)
                word_counts_all[word].append(count)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    faasr_log(f"Aggregated counts per word: {word_counts_all}")

    # Write output files - one per word, containing the list of counts from all mappers
    for i, (word, output_file) in enumerate(zip(words, outputs), start=1):
        counts_list = word_counts_all[word]

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(counts_list, tmp)
            tmp_path = tmp.name

        try:
            faasr_put_file(local_file=tmp_path, remote_folder=folder, remote_file=output_file)
            faasr_log(f"Uploaded shard {i} for word '{word}' with counts {counts_list} to {output_file}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    faasr_log("Shuffle function completed successfully")
