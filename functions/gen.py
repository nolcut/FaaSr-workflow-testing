def gen(N=500, M=1024):
    """
    Generate a synthetic classification dataset, preprocess it (StandardScaler +
    train/test split), and persist the preprocessed arrays to S3 so that the
    downstream classifier training functions can consume them concurrently.
    """
    import numpy as np
    from sklearn.datasets import make_classification
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split

    N = int(N)
    M = int(M)

    faasr_log(f"gen: generating dataset with n_samples={N}, n_features={M}")

    # 1. Generate dataset
    X, y = make_classification(
        n_samples=N,
        n_features=M,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
    )

    # 2. Split BEFORE scaling to avoid leaking test statistics into training
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.4, random_state=123
    )

    # 3. Standardize features (fit on train, apply to both)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # 4. Persist preprocessed arrays locally then upload to S3
    np.save("X_train.npy", X_train)
    np.save("X_test.npy", X_test)
    np.save("y_train.npy", y_train)
    np.save("y_test.npy", y_test)

    for fname in ["X_train.npy", "X_test.npy", "y_train.npy", "y_test.npy"]:
        faasr_put_file(local_file=fname, remote_folder="ml-data", remote_file=fname)

    faasr_log(
        "gen: preprocessing complete; uploaded X_train/X_test/y_train/y_test to "
        "ml-data/ in the default datastore"
    )
