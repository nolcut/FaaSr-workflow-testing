def train_rf():
    """
    Train a Random Forest classifier (max_depth=5, n_estimators=10, no seeding)
    on the preprocessed dataset produced by gen(), report accuracy via clf.score,
    and persist the accuracy result back to S3.
    """
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier

    # Download preprocessed arrays produced by gen()
    for fname in ["X_train.npy", "X_test.npy", "y_train.npy", "y_test.npy"]:
        faasr_get_file(remote_folder="ml-data", remote_file=fname, local_file=fname)

    X_train = np.load("X_train.npy")
    X_test = np.load("X_test.npy")
    y_train = np.load("y_train.npy")
    y_test = np.load("y_test.npy")

    faasr_log("train_rf: training RandomForestClassifier(max_depth=5, n_estimators=10)")

    # No seeding as specified in the prompt
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    clf.fit(X_train, y_train)

    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_rf: Random Forest test accuracy = {accuracy}")

    with open("rf_accuracy.txt", "w") as f:
        f.write(f"Random Forest (max_depth=5, n_estimators=10) accuracy: {accuracy}\n")

    faasr_put_file(
        local_file="rf_accuracy.txt",
        remote_folder="ml-results",
        remote_file="rf_accuracy.txt",
    )
