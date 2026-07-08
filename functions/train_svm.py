def train_svm(folder="ml_data"):
    """
    Train a linear Support Vector Machine on the preprocessed dataset produced
    by `gen` and report its accuracy on the held-out test set.
    """
    import numpy as np
    from sklearn.svm import SVC

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

    faasr_log("train_svm: training SVC(kernel='linear', C=0.025)")

    clf = SVC(kernel="linear", C=0.025)
    clf.fit(X_train, y_train)

    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_svm: SVM test accuracy = {accuracy}")

    # Persist the result
    with open("svm_accuracy.txt", "w") as f:
        f.write(str(accuracy))
    faasr_put_file(
        local_folder=".",
        local_file="svm_accuracy.txt",
        remote_folder=folder,
        remote_file="svm_accuracy.txt",
    )
