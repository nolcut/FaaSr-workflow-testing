import numpy as np
from sklearn.svm import SVC


def svm():
    """Train a linear-kernel Support Vector Machine on the generated dataset and
    report its test accuracy."""
    faasr_log("svm: downloading dataset")

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

    # Support Vector Machine: linear kernel, C = 0.025
    clf = SVC(kernel="linear", C=0.025)
    clf.fit(X_train, y_train)

    accuracy = clf.score(X_test, y_test)
    faasr_log(f"svm: SVC(kernel=linear, C=0.025) test accuracy = {accuracy}")

    with open("svm_accuracy.txt", "w") as f:
        f.write(f"SVM (linear, C=0.025) accuracy: {accuracy}\n")

    faasr_put_file(
        local_file="svm_accuracy.txt",
        remote_folder="ml-pipeline/results",
        remote_file="svm_accuracy.txt",
    )
