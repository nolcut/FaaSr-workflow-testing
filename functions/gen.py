def gen(folder: str, output1: str) -> None:
    import pandas as pd
    from sklearn.datasets import make_classification

    faasr_log("gen: generating synthetic classification dataset with make_classification")

    X, y = make_classification(
        n_samples=500,
        n_features=1024,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
    )

    faasr_log(f"gen: generated X with shape {X.shape} and y with shape {y.shape}")

    feature_columns = [f"feature_{i}" for i in range(X.shape[1])]
    df = pd.DataFrame(X, columns=feature_columns)
    df["target"] = y

    local_file = "raw_dataset.csv"
    df.to_csv(local_file, index=False)

    faasr_log(f"gen: wrote dataset with {df.shape[0]} rows and {df.shape[1]} columns to {local_file}")

    faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)

    faasr_log(f"gen: uploaded {output1} to folder {folder}")
