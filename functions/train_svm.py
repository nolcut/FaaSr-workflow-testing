def train_svm():
    """
    Train a linear Support Vector Machine (SVC, kernel='linear', C=0.025) on the
    preprocessed dataset produced by gen(), report accuracy via clf.score, and
    persist the accuracy result back to S3.
    """
    import numpy as np
    from sklearn.svm import SVC

    # Download preprocessed arrays produced by gen()
    for fname in ["X_train.npy", "X_test.npy", "y_train.npy", "y_test.npy"]:
        faasr_get_file(remote_folder="ml-data", remote_file=fname, local_file=fname)

    X_train = np.load("X_train.npy")
    X_test = np.load("X_test.npy")
    y_train = np.load("y_train.npy")
    y_test = np.load("y_test.npy")

    faasr_log("train_svm: training SVC(kernel='linear', C=0.025)")

    clf = SVC(kernel="linear", C=0.025)
    clf.fit(X_train, y_train)

    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_svm: SVM test accuracy = {accuracy}")

    with open("svm_accuracy.txt", "w") as f:
        f.write(f"SVM (linear, C=0.025) accuracy: {accuracy}\n")

    faasr_put_file(
        local_file="svm_accuracy.txt",
        remote_folder="ml-results",
        remote_file="svm_accuracy.txt",
    )
