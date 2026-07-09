def train_rf(folder="ml_data"):
    """
    Train a Random Forest classifier on the preprocessed dataset produced by
    `gen` and report its accuracy on the held-out test set.
    """
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier

    # Download the preprocessed dataset from S3
    faasr_get_file(
        remote_folder=folder,
        remote_file="dataset.npz",
        local_folder=".",
        local_file="dataset.npz",
    )

    data = np.load("dataset.npz")
    X_train, X_test = data["X_train"], data["X_test"]
    y_train, y_test = data["y_train"], data["y_test"]

    faasr_log("train_rf: training RandomForestClassifier(max_depth=5, n_estimators=10)")

    # No seeding as requested
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    clf.fit(X_train, y_train)

    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_rf: Random Forest test accuracy = {accuracy}")

    # Persist the result
    with open("rf_accuracy.txt", "w") as f:
        f.write(str(accuracy))
    faasr_put_file(
        local_folder=".",
        local_file="rf_accuracy.txt",
        remote_folder=folder,
        remote_file="rf_accuracy.txt",
    )
