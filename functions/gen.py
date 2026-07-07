def gen(folder: str, output1: str, output2: str, output3: str, output4: str) -> None:
    import numpy as np
    from sklearn.datasets import make_classification
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    faasr_log("gen: generating synthetic binary classification dataset with make_classification")

    X, y = make_classification(
        n_samples=500,
        n_features=1024,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
    )

    faasr_log(f"gen: generated data X shape={X.shape}, y shape={y.shape}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.4, random_state=123
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    faasr_log(
        f"gen: split and scaled data X_train={X_train.shape}, X_test={X_test.shape}"
    )

    np.save("X_train.npy", X_train)
    np.save("X_test.npy", X_test)
    np.save("y_train.npy", y_train)
    np.save("y_test.npy", y_test)

    faasr_put_file(local_file="X_train.npy", remote_folder=folder, remote_file=output1)
    faasr_put_file(local_file="X_test.npy", remote_folder=folder, remote_file=output2)
    faasr_put_file(local_file="y_train.npy", remote_folder=folder, remote_file=output3)
    faasr_put_file(local_file="y_test.npy", remote_folder=folder, remote_file=output4)

    faasr_log("gen: uploaded preprocessed train/test features and labels")
