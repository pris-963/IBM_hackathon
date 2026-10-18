
from pathlib import Path
import warnings

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report


# --------------------------------------------------
# 1. PATHS AND CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "air_quality_clean.csv"
)

ARTIFACT_DIR = PROJECT_ROOT / "ml" / "artifacts"

MODEL_FILE = ARTIFACT_DIR / "environment_anomaly_model.joblib"
TEST_FEATURES_FILE = ARTIFACT_DIR / "test_features.csv"
EVALUATION_FILE = ARTIFACT_DIR / "training_evaluation.csv"

# Isolation Forest settings.
CONTAMINATION = 0.05
RANDOM_STATE = 42
TRAIN_RATIO = 0.80

# Original Air Quality dataset feature names.
EXPECTED_FEATURES = [
    "CO(GT)",
    "PT08.S1(CO)",
    "NMHC(GT)",
    "C6H6(GT)",
    "PT08.S2(NMHC)",
    "NOx(GT)",
    "PT08.S3(NOx)",
    "NO2(GT)",
    "PT08.S4(NO2)",
    "PT08.S5(O3)",
    "T",
    "RH",
    "AH",
]


# --------------------------------------------------
# 2. LOAD DATA
# --------------------------------------------------

def load_data(path):
    """Load cleaned data while preserving feature-name capitalization."""

    if not path.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found:\n{path}\n\n"
            "Run this command first:\n"
            "python preprocessing/prepare_data.py"
        )

    print(f"Loading dataset: {path}")

    df = pd.read_csv(path)

    # Remove extra spaces, but preserve feature-name capitalization.
    df.columns = df.columns.astype(str).str.strip()

    # Accept either Timestamp or timestamp.
    timestamp_column = next(
        (
            col for col in df.columns
            if col.strip().lower() == "timestamp"
        ),
        None,
    )

    if timestamp_column is None:
        raise ValueError(
            "Timestamp column not found.\n"
            f"Available columns: {df.columns.tolist()}"
        )

    if timestamp_column != "timestamp":
        df = df.rename(
            columns={timestamp_column: "timestamp"}
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df = df.dropna(subset=["timestamp"]).copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    print(f"Rows loaded: {len(df):,}")
    print(f"Columns found: {df.columns.tolist()}")

    return df


# --------------------------------------------------
# 3. PREPARE FEATURES
# --------------------------------------------------

def prepare_features(df):
    """Validate expected columns and convert them to numeric values."""

    missing = [
        feature
        for feature in EXPECTED_FEATURES
        if feature not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Required features missing: {missing}\n"
            f"Available columns: {df.columns.tolist()}\n\n"
            "Check the columns in data/processed/air_quality_clean.csv. "
            "The cleaned file must contain the original Air Quality "
            "measurement columns."
        )

    # Use the original feature names.
    features = df[EXPECTED_FEATURES].copy()

    for column in EXPECTED_FEATURES:
        features[column] = pd.to_numeric(
            features[column],
            errors="coerce",
        )

    # Convert infinities into missing values.
    features = features.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    # -200 represents missing readings in the original dataset.
    features = features.replace(-200, np.nan)

    # Drop features that have no usable observations.
    all_missing = [
        column
        for column in features.columns
        if features[column].notna().sum() == 0
    ]

    if all_missing:
        raise ValueError(
            f"These features contain no usable values: {all_missing}"
        )

    # Keep timestamps aligned with their corresponding observations.
    valid_rows = features.notna().any(axis=1)

    features = features.loc[valid_rows].reset_index(drop=True)
    timestamps = (
        df.loc[valid_rows, "timestamp"]
        .reset_index(drop=True)
    )

    if len(features) < 20:
        raise ValueError(
            f"Only {len(features)} usable rows remain. "
            "Check your input dataset."
        )

    print(f"Usable rows: {len(features):,}")
    print(f"Number of features: {len(EXPECTED_FEATURES)}")

    return features, timestamps


# --------------------------------------------------
# 4. TRAIN MODEL
# --------------------------------------------------

def main():
    print("=" * 60)
    print("ENVIRONMENTAL ANOMALY DETECTION - MODEL TRAINING")
    print("=" * 60)

    ARTIFACT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Load and prepare the dataset.
    df = load_data(DATA_FILE)
    features, timestamps = prepare_features(df)

    # Split chronologically to avoid randomly mixing earlier
    # and later observations.
    split_index = int(len(features) * TRAIN_RATIO)

    split_index = max(
        1,
        min(split_index, len(features) - 1),
    )

    X_train = features.iloc[:split_index].copy()
    X_test = features.iloc[split_index:].copy()

    test_timestamps = timestamps.iloc[split_index:].copy()

    print(f"\nTraining rows: {len(X_train):,}")
    print(f"Testing rows:  {len(X_test):,}")

    # Impute missing values and scale measurements.
    # Scaling is not strictly required by Isolation Forest,
    # but keeps preprocessing consistent for downstream use.
    model = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "isolation_forest",
                IsolationForest(
                    n_estimators=100,
                    contamination=CONTAMINATION,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    print("\nTraining Isolation Forest...")
    model.fit(X_train)

    print("Training completed.")

    # --------------------------------------------------
    # 5. EVALUATE ON HELD-OUT DATA
    # --------------------------------------------------

    print("\nEvaluating on the held-out test data...")

    # Isolation Forest returns:
    #  1 = normal
    # -1 = anomaly
    raw_predictions = model.predict(X_test)

    # Convert to dashboard-friendly labels:
    # 0 = normal, 1 = anomaly
    anomaly_labels = (raw_predictions == -1).astype(int)

    # Higher scores mean more normal; lower scores mean
    # more unusual observations.
    anomaly_scores = model.decision_function(X_test)

    evaluation = pd.DataFrame(
        {
            "timestamp": test_timestamps,
            "anomaly_score": anomaly_scores,
            "is_anomaly": anomaly_labels,
        }
    )

    evaluation.to_csv(
        EVALUATION_FILE,
        index=False,
    )

    # Save test features with their predictions for the
    # separate evaluation script.
    test_output = X_test.reset_index(drop=True).copy()
    test_output.insert(
        0,
        "timestamp",
        test_timestamps.reset_index(drop=True),
    )
    test_output["anomaly_score"] = anomaly_scores
    test_output["is_anomaly"] = anomaly_labels

    test_output.to_csv(
        TEST_FEATURES_FILE,
        index=False,
    )

    normal_count = int((anomaly_labels == 0).sum())
    anomaly_count = int((anomaly_labels == 1).sum())

    print("\nEvaluation summary")
    print("-" * 40)
    print(f"Test observations: {len(X_test):,}")
    print(f"Normal observations: {normal_count:,}")
    print(f"Anomalies detected: {anomaly_count:,}")

    if len(anomaly_labels):
        print(
            f"Detected anomaly percentage: "
            f"{100 * anomaly_count / len(anomaly_labels):.2f}%"
        )

    print(
        "\nNote: the dataset does not provide verified anomaly labels "
        "for this task. These counts describe the model's predictions; "
        "they are not classification accuracy."
    )

    # --------------------------------------------------
    # 6. SAVE MODEL AND METADATA
    # --------------------------------------------------

    artifact = {
        "model": model,
        "features": EXPECTED_FEATURES,
        "contamination": CONTAMINATION,
        "random_state": RANDOM_STATE,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "model_type": "IsolationForest",
    }

    joblib.dump(
        artifact,
        MODEL_FILE,
        compress=3,
    )

    print("\nFiles saved:")
    print(f"Model: {MODEL_FILE}")
    print(f"Test predictions: {TEST_FEATURES_FILE}")
    print(f"Evaluation results: {EVALUATION_FILE}")

    print("\nModel training completed successfully.")


if __name__ == "__main__":
    warnings.filterwarnings(
        "ignore",
        category=UserWarning,
    )
    main()
