"""Generate a synthetic classification dataset using sklearn's make_classification."""

import os
import tempfile

import pandas as pd
from sklearn.datasets import make_classification

try:
    from faasr import faasr_log, faasr_put_file
except ImportError:
    # For testing with stubs
    pass


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "synthetic_dataset.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: generate_dataset must produce synthetic_dataset.csv containing the generated classification dataset")
        raise SystemExit(1)
# --- end contract helpers ---


def generate_dataset(folder: str, output1: str) -> None:
    """Generate synthetic classification dataset with 500 samples and 1024 features.

    Creates a dataset using sklearn's make_classification, combines features and
    target labels into a DataFrame with columns 'feature_0' through 'feature_1023'
    and 'target', then uploads to S3.

    Args:
        folder: Remote S3 folder path
        output1: Output filename for the synthetic dataset CSV
    """
    faasr_log("Starting synthetic dataset generation")

    # Generate synthetic classification dataset
    # Using make_classification with 500 samples and 1024 features
    n_samples = 500
    n_features = 1024

    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=10,  # Number of informative features
        n_redundant=10,    # Number of redundant features
        n_classes=2,       # Binary classification
        random_state=42    # For reproducibility
    )

    faasr_log(f"Generated dataset with {n_samples} samples and {n_features} features")

    # Create column names for features
    feature_columns = [f"feature_{i}" for i in range(n_features)]

    # Create DataFrame with features
    df = pd.DataFrame(X, columns=feature_columns)

    # Add target column
    df["target"] = y

    faasr_log(f"DataFrame shape: {df.shape}, columns: feature_0 to feature_1023 + target")

    # Save to temporary file and upload
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        tmp_path = tmp.name
        df.to_csv(tmp_path, index=False)

    try:
        faasr_put_file(local_file=tmp_path, remote_folder=folder, remote_file=output1)
        faasr_log(f"Successfully uploaded {output1} to {folder}")
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    faasr_log("Dataset generation complete")
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---