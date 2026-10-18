
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


# --------------------------------------------------
# 1. PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ARTIFACT_DIR = PROJECT_ROOT / "ml" / "artifacts"

MODEL_FILE = ARTIFACT_DIR / "environment_anomaly_model.joblib"

TEST_FEATURES_FILE = ARTIFACT_DIR / "test_features.csv"

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

RESULTS_FILE = OUTPUT_DIR / "evaluation_results.csv"


# --------------------------------------------------
# 2. LOAD MODEL ARTIFACT
# --------------------------------------------------

def load_model_artifact(path):
    """Load the trained model and its metadata."""

    if not path.exists():
        raise FileNotFoundError(
            f"Trained model not found:\n{path}\n\n"
            "Train the model first using:\n"
            "python ml/train_model.py"
        )

    print(f"Loading model: {path}")

    artifact = joblib.load(path)

    # The current train_model.py saves a dictionary.
    if not isinstance(artifact, dict):
        raise ValueError(
            "Unexpected model artifact format. "
            "Expected a dictionary containing the model and metadata."
        )

    if "model" not in artifact:
        raise ValueError(
            "The saved artifact does not contain a 'model' entry."
        )

    model = artifact["model"]

    # Support both the current and older metadata key names.
    algorithm = artifact.get(
        "algorithm",
        artifact.get("model_type", type(model).__name__),
    )

    features = artifact.get("features", [])

    print(f"Model type: {algorithm}")

    return artifact, model, algorithm, features


# --------------------------------------------------
# 3. LOAD TEST DATA
# --------------------------------------------------

def load_test_data(path, expected_features):
    """Load held-out test features created during training."""

    if not path.exists():
        raise FileNotFoundError(
            f"Test feature file not found:\n{path}\n\n"
            "Run the training script first:\n"
            "python ml/train_model.py"
        )

    print(f"Loading test data: {path}")

    df = pd.read_csv(path)

    # Normalize timestamp naming only.
    df.columns = df.columns.astype(str).str.strip()

    timestamp_column = next(
        (
            col for col in df.columns
            if col.lower() == "timestamp"
        ),
        None,
    )

    if timestamp_column is not None and timestamp_column != "timestamp":
        df = df.rename(
            columns={timestamp_column: "timestamp"}
        )

    # Prefer the feature list saved with the model.
    # Fall back to the original Air Quality feature names.
    if not expected_features:
        expected_features = [
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

    # Ignore columns already containing previous predictions.
    missing = [
        col for col in expected_features
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Test data is missing model features: {missing}\n"
            f"Available columns: {df.columns.tolist()}\n"
            "Regenerate the test features by running "
            "python ml/train_model.py."
        )

    X_test = df[expected_features].copy()

    for col in expected_features:
        X_test[col] = pd.to_numeric(
            X_test[col],
            errors="coerce",
        )

    X_test = X_test.replace(
        [np.inf, -np.inf, -200],
        np.nan,
    )

    # The trained pipeline includes a median imputer.
    # Retain rows with at least one valid feature.
    valid_rows = X_test.notna().any(axis=1)

    X_test = X_test.loc[valid_rows].copy()
    output_df = df.loc[valid_rows].copy()

    if X_test.empty:
        raise ValueError(
            "No usable test observations were found."
        )

    print(f"Test observations: {len(X_test):,}")

    return X_test, output_df, expected_features


# --------------------------------------------------
# 4. EVALUATE MODEL
# --------------------------------------------------

def evaluate_model(model, X_test, output_df):
    """
    Predict anomalies.

    Isolation Forest:
       1 = normal
      -1 = anomaly

    Output:
       0 = normal
       1 = anomaly
    """

    print("\nRunning anomaly detection...")

    raw_predictions = model.predict(X_test)

    # Convert Isolation Forest predictions to 0/1.
    is_anomaly = (raw_predictions == -1).astype(int)

    # Lower decision_function values indicate more unusual data.
    anomaly_scores = model.decision_function(X_test)

    results = output_df.copy()

    results["anomaly_score"] = anomaly_scores
    results["is_anomaly"] = is_anomaly
    results["prediction"] = np.where(
        is_anomaly == 1,
        "Anomaly",
        "Normal",
    )

    return results


# --------------------------------------------------
# 5. SAVE RESULTS
# --------------------------------------------------

def save_results(results, path):
    """Save evaluation results to CSV."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    results.to_csv(
        path,
        index=False,
        encoding="utf-8",
    )

    print(f"\nEvaluation results saved to:\n{path}")


# --------------------------------------------------
# 6. PRINT SUMMARY
# --------------------------------------------------

def print_summary(artifact, algorithm, results):
    """Display the model metadata and anomaly summary."""

    total = len(results)

    anomaly_count = int(
        (results["is_anomaly"] == 1).sum()
    )

    normal_count = total - anomaly_count

    anomaly_percentage = (
        anomaly_count / total * 100
        if total > 0
        else 0
    )

    print("\n" + "=" * 55)
    print("ENVIRONMENTAL ANOMALY DETECTION - EVALUATION")
    print("=" * 55)

    print(f"\nModel:                 {algorithm}")
    print(
        f"Training observations: "
        f"{artifact.get('train_rows', 'Not recorded')}"
    )
    print(
        f"Testing observations:  "
        f"{artifact.get('test_rows', total)}"
    )
    print(
        f"Contamination setting: "
        f"{artifact.get('contamination', 'Not recorded')}"
    )

    print("\nPrediction summary")
    print("-" * 35)
    print(f"Total evaluated:       {total:,}")
    print(f"Normal observations:   {normal_count:,}")
    print(f"Anomalies detected:    {anomaly_count:,}")
    print(f"Anomaly percentage:    {anomaly_percentage:.2f}%")

    print("\nMost unusual observations")
    print("-" * 35)

    columns_to_show = [
        col for col in [
            "timestamp",
            "anomaly_score",
            "prediction",
        ]
        if col in results.columns
    ]

    unusual = results.nsmallest(
        min(10, len(results)),
        "anomaly_score",
    )

    if not unusual.empty:
        print(
            unusual[columns_to_show].to_string(index=False)
        )
    else:
        print("No observations available.")

    print("\nImportant:")
    print(
        "The Air Quality dataset does not provide verified "
        "anomaly labels for this project. Therefore, the anomaly "
        "percentage is a model prediction summary, not classification "
        "accuracy, precision, or recall."
    )

    print("\nEvaluation completed successfully.")
    print("=" * 55)


# --------------------------------------------------
# 7. MAIN
# --------------------------------------------------

def main():
    artifact, model, algorithm, features = load_model_artifact(
        MODEL_FILE
    )

    X_test, test_data, features = load_test_data(
        TEST_FEATURES_FILE,
        features,
    )

    results = evaluate_model(
        model,
        X_test,
        test_data,
    )

    save_results(
        results,
        RESULTS_FILE,
    )

    print_summary(
        artifact,
        algorithm,
        results,
    )


if __name__ == "__main__":
    main()
