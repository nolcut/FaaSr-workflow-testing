import json
import random


def split(folder: str, output1: str, output2: str, output3: str) -> None:
    """
    Generate input text with exactly 5000 words from vocabulary [cat, dog, bird, horse, pig],
    each appearing exactly 1000 times. Shuffle with fixed seed and partition into 3 batches
    for parallel map processing.
    """
    faasr_log("Starting split: generating 5000 words from vocabulary")

    # Vocabulary with M=5 different words
    vocabulary = ["cat", "dog", "bird", "horse", "pig"]

    # Generate exactly 5000 words with 1000 of each (evenly distributed)
    words = []
    for word in vocabulary:
        words.extend([word] * 1000)

    faasr_log(f"Generated {len(words)} words with {len(vocabulary)} unique words")

    # Shuffle with fixed random seed for reproducibility
    random.seed(42)
    random.shuffle(words)

    faasr_log("Shuffled words with fixed seed for reproducibility")

    # Partition into N=3 batches:
    # Batches 1 and 2 get 1667 words each, batch 3 gets 1666 words
    batch1 = words[0:1667]      # 1667 words
    batch2 = words[1667:3334]   # 1667 words
    batch3 = words[3334:5000]   # 1666 words

    faasr_log(f"Partitioned into 3 batches: {len(batch1)}, {len(batch2)}, {len(batch3)} words")

    # Write each batch as JSON to local temp files and upload
    batches = [
        (batch1, output1),
        (batch2, output2),
        (batch3, output3)
    ]

    for batch_data, output_file in batches:
        local_file = f"temp_{output_file}"
        with open(local_file, 'w') as f:
            json.dump(batch_data, f)
        faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output_file)
        faasr_log(f"Uploaded {output_file} with {len(batch_data)} words")

    faasr_log("Split complete: 3 batches ready for parallel map processing")
