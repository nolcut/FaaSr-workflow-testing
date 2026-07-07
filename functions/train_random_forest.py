def train_random_forest(folder: str, input1: str, input2: str, input3: str, input4: str, output1: str) -> None:
    import json
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier

    faasr_log("train_random_forest: downloading preprocessed train/test split arrays")

    faasr_get_file(local_file="X_train.npy", remote_folder=folder, remote_file=input1)
    faasr_get_file(local_file="X_test.npy", remote_folder=folder, remote_file=input2)
    faasr_get_file(local_file="y_train.npy", remote_folder=folder, remote_file=input3)
    faasr_get_file(local_file="y_test.npy", remote_folder=folder, remote_file=input4)

    X_train = np.load("X_train.npy")
    X_test = np.load("X_test.npy")
    y_train = np.load("y_train.npy")
    y_test = np.load("y_test.npy")

    faasr_log(
        f"train_random_forest: loaded X_train={X_train.shape}, X_test={X_test.shape}, "
        f"y_train={y_train.shape}, y_test={y_test.shape}"
    )

    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    clf.fit(X_train, y_train)

    accuracy = float(clf.score(X_test, y_test))
    faasr_log(f"train_random_forest: RandomForest test-set accuracy = {accuracy}")

    result = {"classifier": "RandomForest", "accuracy": accuracy}

    with open("random_forest_result.json", "w") as f:
        json.dump(result, f)

    faasr_put_file(local_file="random_forest_result.json", remote_folder=folder, remote_file=output1)

    faasr_log(f"train_random_forest: uploaded {output1}")
