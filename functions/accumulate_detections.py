"""
FaaSr Video Analysis benchmark -- Accumulate (reduce) stage.

Runs exactly once, after all N parallel ``detect_objects`` invocations have
finished (FaaSr synchronizes descendants of a ranked action). It downloads
every per-rank result Yi (``detections_<rank>.json``), accumulates them into a
single final payload Y, and uploads it as ``output_file``.
"""

import json

from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_invocation_id,
    faasr_log,
    faasr_put_file,
)


def _work_folder() -> str:
    # The input folder for this benchmark is always "video_analysis".
    return f"video_analysis/{faasr_invocation_id()}"


def accumulate_detections(
    num_ranks: int = 2,
    output_file: str = "detections.json",
) -> None:
    """
    Accumulate all per-rank detections into the final payload Y.

    Args:
        num_ranks: Number of detect ranks N whose results should be gathered.
        output_file: Name of the final aggregated output file.
    """
    work_folder = _work_folder()

    accumulated = []  # acc
    for rank in range(1, num_ranks + 1):
        part_file = f"detections_{rank}.json"
        faasr_get_file(
            remote_folder=work_folder,
            remote_file=part_file,
            local_file=part_file,
        )
        with open(part_file, "r") as f:
            yi = json.load(f)
        accumulated.extend(yi)
        faasr_log(f"Accumulated {len(yi)} detections from rank {rank}")

    # Final payload Y.
    payload = {
        "num_detections": len(accumulated),
        "detections": accumulated,
    }
    with open(output_file, "w") as f:
        json.dump(payload, f, indent=2)

    faasr_put_file(
        local_file=output_file,
        remote_folder=work_folder,
        remote_file=output_file,
    )
    faasr_log(
        f"Accumulate complete: {len(accumulated)} total detections from "
        f"{num_ranks} ranks -> {work_folder}/{output_file}"
    )
