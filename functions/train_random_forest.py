def train_random_forest(folder: str, input1: str, input2: str, output1: str) -> None:
    import json
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier

    faasr_log("train_random_forest: starting")

    local_train = "train_set.csv"
    local_test = "test_set.csv"

    faasr_get_file(local_file=local_train, remote_folder=folder, remote_file=input1)
    faasr_log(f"train_random_forest: downloaded {input1} from folder {folder}")

    faasr_get_file(local_file=local_test, remote_folder=folder, remote_file=input2)
    faasr_log(f"train_random_forest: downloaded {input2} from folder {folder}")

    train_df = pd.read_csv(local_train)
    test_df = pd.read_csv(local_test)
    faasr_log(
        f"train_random_forest: loaded {train_df.shape[0]} train rows and "
        f"{test_df.shape[0]} test rows"
    )

    if "target" not in train_df.columns or "target" not in test_df.columns:
        msg = "train_random_forest: 'target' column not found in input data"
        faasr_log(msg)
        raise ValueError(msg)

    feature_columns = [c for c in train_df.columns if c != "target"]

    X_train = train_df[feature_columns].values
    y_train = train_df["target"].values
    X_test = test_df[feature_columns].values
    y_test = test_df["target"].values

    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    clf.fit(X_train, y_train)
    faasr_log("train_random_forest: fitted RandomForestClassifier (max_depth=5, n_estimators=10)")

    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_random_forest: test-set accuracy = {accuracy}")

    local_output = "random_forest_accuracy.json"
    with open(local_output, "w") as f:
        json.dump({"accuracy": float(accuracy)}, f)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"train_random_forest: uploaded {output1} to folder {folder}")
