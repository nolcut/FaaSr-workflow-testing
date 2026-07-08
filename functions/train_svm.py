def train_svm(folder="ml-pipeline"):
    """
    Train a linear Support Vector Machine on the preprocessed dataset
    and report its test-set accuracy.
    """
    import numpy as np
    from sklearn.svm import SVC

    # ---- Load preprocessed data from S3 ----
    faasr_get_file(remote_folder=folder, remote_file="dataset.npz", local_file="dataset.npz")
    data = np.load("dataset.npz")
    X_train, X_test = data["X_train"], data["X_test"]
    y_train, y_test = data["y_train"], data["y_test"]

    # ---- Train SVM classifier ----
    clf = SVC(kernel="linear", C=0.025)
    clf.fit(X_train, y_train)

    # ---- Evaluate ----
    accuracy = clf.score(X_test, y_test)
    faasr_log(f"train_svm: SVC(kernel=linear, C=0.025) test accuracy = {accuracy}")

    # ---- Persist result ----
    with open("svm_accuracy.txt", "w") as f:
        f.write(f"SVM accuracy: {accuracy}\n")
    faasr_put_file(
        local_file="svm_accuracy.txt", remote_folder=folder, remote_file="svm_accuracy.txt"
    )
