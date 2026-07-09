import json
import os
import random


def generate_input_text(folder: str, output1: str) -> None:
    # Benchmark parameters (hardcoded internally per the workflow spec):
    #   W = 5000 total words, drawn from an M = 5 word vocabulary, each word
    #   appearing evenly W/M = 1000 times, then shuffled into random order.
    vocabulary = ["cat", "dog", "bird", "horse", "pig"]
    total_words = 5000
    per_word = total_words // len(vocabulary)

    faasr_log(
        f"generate_input_text: building {total_words} words from "
        f"{len(vocabulary)} vocab terms {vocabulary}, {per_word} each"
    )

    # Even distribution: each vocabulary word repeated per_word times.
    words = []
    for w in vocabulary:
        words.extend([w] * per_word)

    # Shuffle the full sequence into random order.
    random.shuffle(words)

    faasr_log(f"generate_input_text: shuffled sequence of {len(words)} words")

    # Write the sequence as a JSON list to a local temp file, then upload.
    local_file = "input_text.json"
    with open(local_file, "w") as f:
        json.dump(words, f)

    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
    faasr_log(f"generate_input_text: wrote '{output1}' to folder '{folder}'")

    if os.path.exists(local_file):
        os.remove(local_file)
