import json
import os
import random


def generate_input_text(folder: str, output1: str) -> None:
    # MapReduce benchmark parameters (hardcoded constants — no external config).
    VOCABULARY = ["cat", "dog", "bird", "horse", "pig"]  # M = 5 different words
    TOTAL_WORDS = 5000                                   # W = 5000 total words
    SEED = 42                                            # fixed seed for reproducibility

    faasr_log(
        f"generate_input_text: building corpus of W={TOTAL_WORDS} words "
        f"from vocabulary {VOCABULARY} (M={len(VOCABULARY)})"
    )

    if TOTAL_WORDS % len(VOCABULARY) != 0:
        raise ValueError(
            f"TOTAL_WORDS ({TOTAL_WORDS}) is not evenly divisible by "
            f"vocabulary size ({len(VOCABULARY)})"
        )

    # Distribute evenly: 5000 / 5 = 1000 occurrences of each vocabulary word.
    per_word = TOTAL_WORDS // len(VOCABULARY)
    words = []
    for w in VOCABULARY:
        words.extend([w] * per_word)

    # Shuffle the full list randomly so word order is randomized.
    random.seed(SEED)
    random.shuffle(words)

    faasr_log(f"generate_input_text: assembled {len(words)} words, writing JSON array")

    local_file = "raw_input_text.json"
    with open(local_file, "w") as f:
        json.dump(words, f)

    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
    faasr_log(f"generate_input_text: uploaded {output1} to folder '{folder}'")

    if os.path.exists(local_file):
        os.remove(local_file)
