def gen(N=500, M=1024, folder="ml_data"):
    """
    Generate a synthetic classification dataset, preprocess it, and persist the
    train/test splits to S3 so that the downstream classifier functions can
    consume them concurrently.
    """
    import numpy as np
    from sklearn.datasets import make_classification
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split

    # Coerce arguments (workflow arguments may arrive as strings)
    N = int(N)
    M = int(M)

    faasr_log(f"gen: generating dataset with n_samples={N}, n_features={M}")

    # 1. Generate the dataset
    X, y = make_classification(
        n_samples=N,
        n_features=M,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
    )

    # 2. Split into train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.4, random_state=123
    )

    # 3. Standardize features (fit on train, apply to both)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # 4. Persist the preprocessed splits locally then upload to S3
    local_file = "dataset.npz"
    np.savez(
        local_file,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
    )

    faasr_put_file(
        local_folder=".",
        local_file=local_file,
        remote_folder=folder,
        remote_file="dataset.npz",
    )

    faasr_log(
        f"gen: wrote preprocessed dataset to {folder}/dataset.npz "
        f"(train={X_train.shape}, test={X_test.shape})"
    )
