import random
import tempfile
import os


def split(folder: str, output1: str, output2: str, output3: str) -> None:
    """
    Generate input text containing W=5000 words from vocabulary [cat, dog, bird, horse, pig]
    with each word distributed evenly (1000 of each) and shuffled randomly.
    Partition the resulting text into N=3 batches for parallel processing by the downstream map functions.
    """
    faasr_log("Starting split: generating W=5000 words from vocabulary [cat, dog, bird, horse, pig]")

    # Define vocabulary and parameters
    vocabulary = ["cat", "dog", "bird", "horse", "pig"]
    words_per_vocab = 1000  # 5000 total / 5 words = 1000 each
    total_words = 5000
    num_batches = 3

    # Generate the word list with even distribution
    words = []
    for word in vocabulary:
        words.extend([word] * words_per_vocab)

    # Shuffle randomly
    random.shuffle(words)

    faasr_log(f"Generated {len(words)} words, shuffled randomly")

    # Calculate batch sizes: 5000 / 3 = 1666.67, so batches 1 and 2 get 1667, batch 3 gets 1666
    # This gives approximately equal distribution
    batch_size = total_words // num_batches  # 1666
    remainder = total_words % num_batches     # 2

    # Create batch boundaries
    batches = []
    start = 0
    for i in range(num_batches):
        # Add one extra word to the first 'remainder' batches
        size = batch_size + (1 if i < remainder else 0)
        batches.append(words[start:start + size])
        start += size

    faasr_log(f"Split into {num_batches} batches with sizes: {[len(b) for b in batches]}")

    # Output files mapping
    outputs = [output1, output2, output3]

    # Write each batch to a file and upload
    for i, (batch, output_file) in enumerate(zip(batches, outputs), start=1):
        # Create text content with words separated by spaces
        text_content = " ".join(batch)

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp.write(text_content)
            tmp_path = tmp.name

        try:
            # Upload to S3
            faasr_put_file(local_file=tmp_path, remote_folder=folder, remote_file=output_file)
            faasr_log(f"Uploaded batch {i} ({len(batch)} words) to {output_file}")
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    faasr_log("Split function completed successfully")
