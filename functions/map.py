import json
import tempfile
import os


def map(folder: str, input1: str, output1: str) -> None:
    """
    Count how often each word occurs in the assigned text chunk.
    This is a parallel map function where each instance (identified by its FaaSr rank)
    reads its corresponding batch file from the split phase, counts the frequency of
    each word in that chunk, and outputs the word frequency counts as a JSON file.
    """
    # Get this instance's rank
    r = faasr_rank()
    rank = r['rank']
    max_rank = r['max_rank']

    faasr_log(f"Map function starting for rank {rank}/{max_rank}")

    # Substitute rank into input/output filenames
    input_file = input1.format(rank=rank)
    output_file = output1.format(rank=rank)

    faasr_log(f"Reading input file: {input_file}")

    # Download the text batch file to a temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
        tmp_input_path = tmp.name

    try:
        faasr_get_file(local_file=tmp_input_path, remote_folder=folder, remote_file=input_file)

        # Read the text content
        with open(tmp_input_path, 'r') as f:
            text_content = f.read()

        if not text_content.strip():
            faasr_log(f"ERROR: Input file {input_file} is empty or could not be read")
            raise ValueError(f"Input file {input_file} is empty or missing")

        # Split into words and count frequencies
        words = text_content.split()
        faasr_log(f"Read {len(words)} words from {input_file}")

        # Count word frequencies
        word_counts = {}
        for word in words:
            # Normalize to lowercase (though the input should already be lowercase)
            word_lower = word.lower().strip()
            if word_lower:
                word_counts[word_lower] = word_counts.get(word_lower, 0) + 1

        faasr_log(f"Counted {len(word_counts)} unique words: {word_counts}")

    finally:
        # Clean up input temp file
        if os.path.exists(tmp_input_path):
            os.remove(tmp_input_path)

    # Write word counts to JSON file and upload
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        json.dump(word_counts, tmp)
        tmp_output_path = tmp.name

    try:
        faasr_put_file(local_file=tmp_output_path, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Uploaded word counts to {output_file}")
    finally:
        # Clean up output temp file
        if os.path.exists(tmp_output_path):
            os.remove(tmp_output_path)

    faasr_log(f"Map function completed successfully for rank {rank}")
