import json
import os
import random


def generate_input_text(folder: str, output1: str) -> None:
    # Benchmark-specific dataset generation: W=5000 words drawn evenly from a
    # fixed vocabulary of 5 words, then shuffled randomly (see workflow spec).
    vocabulary = ["cat", "dog", "bird", "horse", "pig"]
    total_words = 5000

    if total_words % len(vocabulary) != 0:
        raise ValueError(
            f"W={total_words} is not evenly divisible by vocabulary size "
            f"{len(vocabulary)}"
        )
    per_word = total_words // len(vocabulary)  # 1000 occurrences each

    faasr_log(
        f"Generating input text: {total_words} words, {len(vocabulary)} distinct "
        f"words ({vocabulary}), {per_word} occurrences each"
    )

    words = []
    for w in vocabulary:
        words.extend([w] * per_word)

    random.shuffle(words)

    if len(words) != total_words:
        raise RuntimeError(
            f"Expected {total_words} words but produced {len(words)}"
        )

    local_file = "input_text.json"
    with open(local_file, "w") as f:
        json.dump(words, f)

    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
    faasr_log(f"Wrote shuffled word list to {folder}/{output1}")

    try:
        os.remove(local_file)
    except OSError:
        pass
