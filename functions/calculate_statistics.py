import json
import statistics


def calculate_statistics(folder: str, input1: str, output1: str) -> None:
    faasr_log(f"Downloading {input1} from {folder}")
    local_input = "/tmp/random_numbers.json"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

    with open(local_input) as f:
        numbers = json.load(f)

    faasr_log(f"Computing mean and median for {len(numbers)} numbers")
    mean = statistics.mean(numbers)
    median = statistics.median(numbers)
    faasr_log(f"mean={mean}, median={median}")

    result = {"mean": mean, "median": median}
    local_output = "/tmp/statistics.json"
    with open(local_output, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log("calculate_statistics complete")
