def accumulate(folder="video_analysis"):
    """
    Reduce phase of the video-analysis benchmark.

    FaaSr's rank barrier guarantees this function runs exactly once, after all N
    parallel `detect` invocations have completed. It downloads every per-rank
    result Yi = detections_<rank>.json, accumulates them into `acc`, and returns
    (and persists) the final payload Y.
    """
    import os
    import json

    # Discover all per-rank detection files produced by the map phase
    remote_folder = f"{folder}/detections"
    contents = faasr_get_folder_list(faasr_prefix=remote_folder)

    acc = []
    used = []
    for entry in contents:
        fname = os.path.basename(entry.rstrip("/"))
        if fname.startswith("detections_") and fname.endswith(".json"):
            faasr_get_file(
                remote_folder=remote_folder,
                remote_file=fname,
                local_folder=".",
                local_file=fname,
            )
            with open(fname) as f:
                acc.extend(json.load(f))
            used.append(fname)

    # Final payload Y: all detections with score > 0.5, each {label, class, score}
    Y = {"detections": acc, "count": len(acc)}
    with open("Y.json", "w") as f:
        json.dump(Y, f, indent=2)
    faasr_put_file(
        local_folder=".",
        local_file="Y.json",
        remote_folder=folder,
        remote_file="Y.json",
    )

    faasr_log(
        f"accumulate: merged {len(used)} result file(s) ({sorted(used)}) into "
        f"{len(acc)} total detection(s); final payload written to {folder}/Y.json"
    )
    return Y
