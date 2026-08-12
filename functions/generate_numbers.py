import json
import numpy as np


def generate_numbers(folder: str, output1: str) -> None:
    faasr_log("Generating 200 random numbers from standard normal distribution")

    numbers = np.random.standard_normal(200).tolist()

    local_file = "/tmp/random_numbers.json"
    with open(local_file, "w") as f:
        json.dump(numbers, f)

    faasr_log(f"Generated {len(numbers)} numbers, uploading to {folder}/{output1}")
    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
    faasr_log("generate_numbers complete")
