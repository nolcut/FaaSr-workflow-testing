def train_random_forest(folder: str, input1: str, output1: str) -> None:
    """Train a Random Forest classifier and report its test accuracy."""
    import os
    import json
    import tempfile

    import numpy as np
    from sklearn.ensemble import RandomForestClassifier

    faasr_log(f"train_random_forest: downloading {input1} from folder {folder}")

    tmp_dir = tempfile.mkdtemp()
    local_json = os.path.join(tmp_dir, input1)
    faasr_get_file(local_file=local_json, remote_folder=folder, remote_file=input1)

    with open(local_json) as f:
        data = json.load(f)

    X_train = np.array(data["X_train"])
    X_test = np.array(data["X_test"])
    y_train = np.array(data["y_train"])
    y_test = np.array(data["y_test"])
    faasr_log(
        f"train_random_forest: loaded train {X_train.shape} and test {X_test.shape}"
    )

    # No seeding per the workflow specification.
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    clf.fit(X_train, y_train)
    faasr_log("train_random_forest: fitted RandomForestClassifier(max_depth=5, n_estimators=10)")

    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_random_forest: test accuracy = {accuracy}")

    result = {"model": "RandomForest", "accuracy": float(accuracy)}

    local_out = os.path.join(tmp_dir, output1)
    with open(local_out, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"train_random_forest: uploaded {output1} to folder {folder}")
