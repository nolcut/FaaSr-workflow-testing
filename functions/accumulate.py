import json

from FaaSr_py.client.py_client_stubs import (
    faasr_get_file,
    faasr_log,
    faasr_put_file,
)


def accumulate(
    folder="video_analysis",
    num_batches=2,
    output_file="detections.json",
):
    """
    Reduce (fan-in) phase.

    Runs after all N parallel ``detect`` invocations complete. Downloads each
    per-rank result Yi (detections_1.json .. detections_N.json), accumulates
    them into ``acc``, and uploads the final payload Y containing every
    detection's {label, class, score} (score > 0.5).
    """
    acc = []

    for rank in range(1, num_batches + 1):
        part_file = f"detections_{rank}.json"
        try:
            faasr_get_file(
                remote_folder=folder,
                remote_file=part_file,
                local_file=part_file,
            )
        except Exception as e:  # noqa: BLE001
            faasr_log(f"accumulate: could not fetch {part_file}: {e}")
            continue

        with open(part_file) as f:
            yi = json.load(f)

        acc.extend(yi)
        faasr_log(f"accumulate: gathered {len(yi)} detection(s) from {part_file}")

    # Final payload Y: keep only the required fields per detection.
    Y = [
        {"label": d["label"], "class": d["class"], "score": d["score"]}
        for d in acc
    ]

    with open(output_file, "w") as f:
        json.dump(Y, f, indent=2)

    faasr_put_file(
        local_file=output_file,
        remote_folder=folder,
        remote_file=output_file,
    )
    faasr_log(
        f"accumulate: wrote final payload Y with {len(Y)} detection(s) "
        f"to {folder}/{output_file}"
    )

    return Y
