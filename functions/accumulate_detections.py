import os
import json
import tempfile


def accumulate_detections(folder: str, input1: str, output1: str) -> None:
    """Accumulate step of the parallelized video object-detection benchmark.

    Reads the per-batch detection outputs produced by each of the N parallel
    `detect_objects` instances (each a JSON array of {label, class, score}
    detections with score > 0.5), concatenates/flattens all detections across
    every ranked output into a single combined collection, and writes the final
    payload as a single JSON output (all_detections.json).

    The number of parallel detect functions is not assumed: the per-rank files
    are discovered from the folder listing rather than a fixed count.
    """
    workdir = tempfile.mkdtemp(prefix="accumulate_detections_")

    # ---- Derive the per-rank filename pattern from input1 ----
    # input1 looks like "batch_detections_{rank}.json"
    if "{rank}" in input1:
        prefix_part, suffix_part = input1.split("{rank}", 1)
    else:
        # No rank placeholder: fall back to matching the literal name.
        prefix_part, suffix_part = input1, ""

    # ---- Discover ALL per-rank detection files in the folder ----
    faasr_log(f"Listing folder '{folder}' for detection files matching '{input1}'")
    all_keys = faasr_get_folder_list(prefix=folder)

    matched_basenames = []
    for key in all_keys:
        basename = key.rsplit("/", 1)[-1]
        if not basename.startswith(prefix_part) or not basename.endswith(suffix_part):
            continue
        # The portion between prefix and suffix is the rank token; it must exist.
        middle = basename[len(prefix_part):]
        if suffix_part:
            middle = middle[:len(middle) - len(suffix_part)]
        if middle == "":
            continue
        matched_basenames.append(basename)

    matched_basenames = sorted(set(matched_basenames))

    if not matched_basenames:
        msg = (
            f"No per-rank detection files matching '{input1}' were found in "
            f"folder '{folder}'. Cannot accumulate detections."
        )
        faasr_log(f"ERROR: {msg}")
        raise RuntimeError(msg)

    faasr_log(f"Found {len(matched_basenames)} detection file(s): {matched_basenames}")

    # ---- Download and flatten every per-rank detection array ----
    acc = []
    for basename in matched_basenames:
        local_path = os.path.join(workdir, basename)
        faasr_log(f"Downloading detection file '{basename}' from folder '{folder}'")
        faasr_get_file(local_file=local_path, remote_folder=folder, remote_file=basename)

        if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
            msg = f"Detection file '{basename}' is missing or empty after download"
            faasr_log(f"ERROR: {msg}")
            raise RuntimeError(msg)

        with open(local_path, "r") as fh:
            detections = json.load(fh)

        if not isinstance(detections, list):
            msg = f"Detection file '{basename}' does not contain a JSON array of detections"
            faasr_log(f"ERROR: {msg}")
            raise RuntimeError(msg)

        faasr_log(f"'{basename}' contributed {len(detections)} detection(s)")
        acc.extend(detections)

    faasr_log(f"Accumulated {len(acc)} total detection(s) from {len(matched_basenames)} shard(s)")

    # ---- Write the final combined payload ----
    local_out = os.path.join(workdir, output1)
    with open(local_out, "w") as fh:
        json.dump(acc, fh)

    faasr_log(f"Uploading combined detections as '{output1}' to folder '{folder}'")
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log("accumulate_detections complete")
