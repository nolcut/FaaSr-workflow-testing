import json

def calculate_mean(folder: str, input1: str, output1: str) -> None:
    local_in = "/tmp/random_numbers.json"
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)
    with open(local_in) as f:
        numbers = json.load(f)
    mean = sum(numbers) / len(numbers)
    faasr_log(f"Computed mean of {len(numbers)} numbers: {mean}")
    local_out = "/tmp/mean_value.json"
    with open(local_out, "w") as f:
        json.dump({"mean": mean}, f)
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"Saved mean to {output1}")
