def gen(N=500, M=1024, folder="ml-pipeline"):
    """
    Generate a synthetic classification dataset, preprocess it
    (StandardScaler + train_test_split), and persist the resulting
    train/test splits to S3 for the downstream classifiers.
    """
    import numpy as np
    from sklearn.datasets import make_classification
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    # ---- Dataset generation ----
    X, y = make_classification(
        n_samples=int(N),
        n_features=int(M),
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
    )
    faasr_log(f"gen: generated dataset with N={N} samples and M={M} features")

    # ---- Preprocess: split then scale (fit scaler on training data only) ----
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.4, random_state=123
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    faasr_log(
        f"gen: split into {X_train.shape[0]} train / {X_test.shape[0]} test samples "
        f"and applied StandardScaler"
    )

    # ---- Persist splits to S3 ----
    local_file = "dataset.npz"
    np.savez(
        local_file,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
    )
    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file="dataset.npz")
    faasr_log(f"gen: uploaded dataset.npz to {folder}/dataset.npz")
