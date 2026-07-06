def preprocess(folder: str, input1: str, output1: str, output2: str) -> None:
    import pandas as pd
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split

    faasr_log("preprocess: starting")

    local_input = "raw_dataset.csv"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)
    faasr_log(f"preprocess: downloaded {input1} from folder {folder}")

    df = pd.read_csv(local_input)
    faasr_log(f"preprocess: loaded dataset with {df.shape[0]} rows and {df.shape[1]} columns")

    if "target" not in df.columns:
        msg = "preprocess: 'target' column not found in input dataset"
        faasr_log(msg)
        raise ValueError(msg)

    feature_columns = [c for c in df.columns if c != "target"]
    X = df[feature_columns].values
    y = df["target"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.4, random_state=123
    )
    faasr_log(
        f"preprocess: split into {X_train.shape[0]} train and {X_test.shape[0]} test samples"
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    faasr_log("preprocess: applied StandardScaler (fit on train, transform on test)")

    train_df = pd.DataFrame(X_train_scaled, columns=feature_columns)
    train_df["target"] = y_train

    test_df = pd.DataFrame(X_test_scaled, columns=feature_columns)
    test_df["target"] = y_test

    local_train = "train_set.csv"
    local_test = "test_set.csv"
    train_df.to_csv(local_train, index=False)
    test_df.to_csv(local_test, index=False)

    faasr_put_file(local_file=local_train, remote_folder=folder, remote_file=output1)
    faasr_log(f"preprocess: uploaded {output1} to folder {folder}")

    faasr_put_file(local_file=local_test, remote_folder=folder, remote_file=output2)
    faasr_log(f"preprocess: uploaded {output2} to folder {folder}")
