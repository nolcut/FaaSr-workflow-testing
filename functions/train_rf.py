import numpy as np
from sklearn.ensemble import RandomForestClassifier


def train_rf(folder="ml"):
    """Train a Random Forest classifier on the generated dataset and
    report its test accuracy."""

    # Download the preprocessed dataset produced by gen
    faasr_get_file(
        remote_folder=folder,
        remote_file="dataset.npz",
        local_file="dataset.npz",
    )

    data = np.load("dataset.npz")
    X_train, X_test = data["X_train"], data["X_test"]
    y_train, y_test = data["y_train"], data["y_test"]

    faasr_log("train_rf: training RandomForestClassifier(max_depth=5, n_estimators=10)")

    # No seeding per the requirements
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    clf.fit(X_train, y_train)

    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_rf: Random Forest test accuracy = {accuracy}")

    # Persist the result
    local_file = "rf_accuracy.txt"
    with open(local_file, "w") as f:
        f.write(f"Random Forest accuracy: {accuracy}\n")

    faasr_put_file(
        local_file=local_file,
        remote_folder=folder,
        remote_file="rf_accuracy.txt",
    )
