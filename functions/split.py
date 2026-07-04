import json
import random


def split(folder: str, output1: str, output2: str, output3: str) -> None:
    """
    Generate input text containing W=5000 words from vocabulary [cat, dog, bird, horse, pig]
    (M=5 different words), with each word distributed evenly (1000 occurrences each) and
    the entire list shuffled randomly. Partition into N=3 batches for parallel map processing.
    """
    faasr_log("Starting split: generating 5000 words with 5 vocabulary items")

    # Vocabulary and parameters per spec
    vocabulary = ["cat", "dog", "bird", "horse", "pig"]
    words_per_term = 1000  # W=5000 total, M=5 words => 1000 each
    n_batches = 3  # N=3 partitions

    # Generate all words: 1000 occurrences of each word
    all_words = []
    for word in vocabulary:
        all_words.extend([word] * words_per_term)

    faasr_log(f"Generated {len(all_words)} words total")

    # Shuffle randomly
    random.shuffle(all_words)
    faasr_log("Shuffled words randomly")

    # Partition into 3 approximately equal batches
    total_words = len(all_words)
    batch_size = total_words // n_batches

    batches = [
        all_words[0:batch_size],                      # batch 1: indices 0-1666
        all_words[batch_size:2*batch_size],           # batch 2: indices 1667-3333
        all_words[2*batch_size:]                      # batch 3: indices 3334-4999 (gets any remainder)
    ]

    output_files = [output1, output2, output3]

    for i, (batch, output_file) in enumerate(zip(batches, output_files), start=1):
        local_file = f"batch_{i}.json"
        with open(local_file, "w") as f:
            json.dump(batch, f)
        faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Wrote batch {i} with {len(batch)} words to {output_file}")

    faasr_log("Split complete: 3 batches created for parallel map processing")
