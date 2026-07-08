import os
import json
import random


def generate_vocabulary(folder: str, output1: str) -> None:
    # Benchmark parameters (see workflow spec / Original User Request):
    #   W = 5000 total words, drawn from an M = 5 word vocabulary,
    #   each word distributed evenly (W/M = 1000 occurrences) then shuffled.
    vocabulary = ["yellow", "orange", "red", "blue", "grey"]
    total_words = 5000

    m = len(vocabulary)
    if total_words % m != 0:
        faasr_log(
            f"generate_vocabulary: W={total_words} is not evenly divisible by "
            f"vocabulary size M={m}; cannot distribute words evenly."
        )
        raise ValueError(
            f"Total words {total_words} not divisible by vocabulary size {m}"
        )

    per_word = total_words // m
    faasr_log(
        f"generate_vocabulary: generating {total_words} words, {per_word} each "
        f"of vocabulary {vocabulary}."
    )

    # Build the evenly-distributed list, then shuffle randomly.
    words = []
    for w in vocabulary:
        words.extend([w] * per_word)
    random.shuffle(words)

    if len(words) != total_words:
        faasr_log(
            f"generate_vocabulary: expected {total_words} tokens but built "
            f"{len(words)}."
        )
        raise ValueError("Generated word list has unexpected length")

    local_file = "input_text.json"
    with open(local_file, "w") as f:
        json.dump(words, f)

    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
    faasr_log(
        f"generate_vocabulary: wrote {len(words)} word tokens to "
        f"{folder}/{output1}."
    )

    if os.path.exists(local_file):
        os.remove(local_file)
