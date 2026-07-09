import numpy as np
from sklearn.ensemble import RandomForestClassifier


def random_forest():
    """Train a Random Forest classifier on the generated dataset and report its
    test accuracy."""
    faasr_log("random_forest: downloading dataset")

    faasr_get_file(
        remote_folder="ml-pipeline",
        remote_file="dataset.npz",
        local_file="dataset.npz",
    )

    data = np.load("dataset.npz")
    X_train = data["X_train"]
    X_test = data["X_test"]
    y_train = data["y_train"]
    y_test = data["y_test"]

    # Random Forest: max_depth=5, n_estimators=10, no seeding
    clf = RandomForestClassifier(max_depth=5, n_estimators=10)
    clf.fit(X_train, y_train)

    accuracy = clf.score(X_test, y_test)
    faasr_log(
        f"random_forest: RandomForestClassifier(max_depth=5, n_estimators=10) "
        f"test accuracy = {accuracy}"
    )

    with open("random_forest_accuracy.txt", "w") as f:
        f.write(f"Random Forest (max_depth=5, n_estimators=10) accuracy: {accuracy}\n")

    faasr_put_file(
        local_file="random_forest_accuracy.txt",
        remote_folder="ml-pipeline/results",
        remote_file="random_forest_accuracy.txt",
    )
