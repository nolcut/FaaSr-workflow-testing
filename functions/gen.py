def gen(folder: str, n_samples: int, n_features: int, output1: str) -> None:
    """Generate a synthetic classification dataset, preprocess it, and persist it to S3.

    Uses make_classification to create N samples with M features, then splits with
    train_test_split and standardizes features with StandardScaler (fit on train only).
    The preprocessed train/test arrays are written to S3 as JSON for downstream classifiers.
    """
    import os
    import json
    import tempfile

    import numpy as np
    from sklearn.datasets import make_classification
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    faasr_log(
        f"gen: generating dataset with n_samples={n_samples}, n_features={n_features}"
    )

    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_redundant=0,
        n_clusters_per_class=2,
        weights=[0.9, 0.1],
        flip_y=0.1,
        random_state=123,
    )
    faasr_log(f"gen: generated X with shape {X.shape} and y with shape {y.shape}")

    # Split into train/test before scaling to avoid leakage.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.4, random_state=123
    )
    faasr_log(
        f"gen: split into train {X_train.shape} and test {X_test.shape} "
        "(test_size=0.4, random_state=123)"
    )

    # Standardize features: fit on training data only, then transform both.
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    faasr_log("gen: standardized features with StandardScaler (fit on train)")

    data = {
        "X_train": X_train.tolist(),
        "X_test": X_test.tolist(),
        "y_train": y_train.tolist(),
        "y_test": y_test.tolist(),
    }

    tmp_dir = tempfile.mkdtemp()
    local_json = os.path.join(tmp_dir, output1)
    with open(local_json, "w") as f:
        json.dump(data, f)
    faasr_log(f"gen: wrote preprocessed data to local file {local_json}")

    faasr_put_file(local_file=local_json, remote_folder=folder, remote_file=output1)
    faasr_log(f"gen: uploaded {output1} to folder {folder}")
