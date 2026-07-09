def train_svm(folder: str, input1: str, output1: str) -> None:
    """Train a linear-kernel SVM classifier and report its test accuracy."""
    import os
    import json
    import tempfile

    import numpy as np
    from sklearn.svm import SVC

    faasr_log(f"train_svm: downloading {input1} from folder {folder}")

    tmp_dir = tempfile.mkdtemp()
    local_json = os.path.join(tmp_dir, input1)
    faasr_get_file(local_file=local_json, remote_folder=folder, remote_file=input1)

    with open(local_json) as f:
        data = json.load(f)

    X_train = np.array(data["X_train"])
    X_test = np.array(data["X_test"])
    y_train = np.array(data["y_train"])
    y_test = np.array(data["y_test"])
    faasr_log(f"train_svm: loaded train {X_train.shape} and test {X_test.shape}")

    clf = SVC(kernel="linear", C=0.025)
    clf.fit(X_train, y_train)
    faasr_log("train_svm: fitted SVC(kernel='linear', C=0.025)")

    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_svm: test accuracy = {accuracy}")

    result = {"model": "SVM", "accuracy": float(accuracy)}

    local_out = os.path.join(tmp_dir, output1)
    with open(local_out, "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"train_svm: uploaded {output1} to folder {folder}")
