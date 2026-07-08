def train_rf(folder="ml-pipeline"):
    """
    Train a Random Forest classifier on the preprocessed dataset
    and report its test-set accuracy.
    """
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier

    # ---- Load preprocessed data from S3 ----
    faasr_get_file(remote_folder=folder, remote_file="dataset.npz", local_file="dataset.npz")
    data = np.load("dataset.npz")
    X_train, X_test = data["X_train"], data["X_test"]
    y_train, y_test = data["y_train"], data["y_test"]

    # ---- Train Random Forest classifier (no seeding) ----
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    clf.fit(X_train, y_train)

    # ---- Evaluate ----
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_rf: RandomForest(max_depth=5, n_estimators=10) test accuracy = {accuracy}")

    # ---- Persist result ----
    with open("rf_accuracy.txt", "w") as f:
        f.write(f"Random Forest accuracy: {accuracy}\n")
    faasr_put_file(
        local_file="rf_accuracy.txt", remote_folder=folder, remote_file="rf_accuracy.txt"
    )
