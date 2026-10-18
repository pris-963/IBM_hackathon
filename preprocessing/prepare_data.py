
from pathlib import Path
import pandas as pd


# --------------------------------------------------
# 1. PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "AirQualityUCI.xlsx"

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

OUTPUT_FILE = OUTPUT_DIR / "air_quality_clean.csv"


# --------------------------------------------------
# 2. LOAD EXCEL DATASET
# --------------------------------------------------

def load_dataset(path):
    """
    Load the Air Quality dataset from an Excel workbook.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}\n"
            "Make sure AirQualityUCI.xlsx is inside data/raw/."
        )

    print(f"Loading Excel dataset: {path}")

    try:
        # Read the first worksheet.
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as exc:
        raise RuntimeError(
            f"Could not read the Excel workbook: {exc}\n"
            "Open the file in Excel and save it as a valid .xlsx workbook."
        ) from exc

    # Clean column names.
    df.columns = df.columns.astype(str).str.strip()

    # Remove completely empty rows and columns.
    df = df.dropna(axis=1, how="all")
    df = df.dropna(how="all").copy()

    print("\nColumns found in the workbook:")
    print(df.columns.tolist())

    # Expected columns from the Air Quality dataset.
    required_columns = {"Date", "Time", "T", "RH", "AH"}

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}\n"
            f"Columns found: {df.columns.tolist()}\n"
            "Check that the workbook contains the original Air Quality data "
            "and that the correct worksheet is being read."
        )

    print(f"\nLoaded {len(df):,} rows successfully.")

    return df


# --------------------------------------------------
# 3. CLEAN DATASET
# --------------------------------------------------

def clean_dataset(df):
    """
    Clean dates, times, numeric measurements and missing values.
    """

    print("\nCleaning dataset...")

    df = df.copy()

    # Remove leading/trailing spaces from text columns.
    df.columns = df.columns.astype(str).str.strip()

    # Remove Excel-generated empty columns, if any.
    df = df.loc[
        :,
        ~df.columns.astype(str).str.startswith("Unnamed")
    ]

    # ----------------------------------------------
    # Clean Date
    # ----------------------------------------------

    # Handles dates stored as Excel dates or text.
    df["Date"] = pd.to_datetime(
        df["Date"],
        dayfirst=True,
        errors="coerce"
    )

    # ----------------------------------------------
    # Clean Time
    # ----------------------------------------------

    def parse_time(value):
        """
        Convert Excel time values or time strings to HH:MM:SS.
        Supports formats such as 18.00.00 and 18:00:00.
        """

        if pd.isna(value):
            return pd.NaT

        # Excel may store time as a Python time/datetime object.
        if hasattr(value, "hour") and hasattr(value, "minute"):
            return pd.to_datetime(
                f"{value.hour:02d}:{value.minute:02d}:"
                f"{getattr(value, 'second', 0):02d}",
                format="%H:%M:%S",
                errors="coerce"
            )

        # Handle numeric Excel time fractions.
        if isinstance(value, (int, float)):
            if 0 <= value < 1:
                total_seconds = round(value * 24 * 60 * 60)
                total_seconds %= 24 * 60 * 60
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60

                return pd.to_datetime(
                    f"{hours:02d}:{minutes:02d}:{seconds:02d}",
                    format="%H:%M:%S",
                    errors="coerce"
                )

        # Handle textual values.
        text_value = str(value).strip()

        if not text_value:
            return pd.NaT

        text_value = text_value.replace(".", ":")

        return pd.to_datetime(
            text_value,
            format="%H:%M:%S",
            errors="coerce"
        )

    parsed_time = df["Time"].apply(parse_time)

    df["Time"] = parsed_time.dt.strftime("%H:%M:%S")

    # ----------------------------------------------
    # Clean numeric sensor measurements
    # ----------------------------------------------

    numeric_columns = [
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
        "AH"
    ]

    # Convert only columns that actually exist.
    for column in numeric_columns:
        if column in df.columns:
            # Support numbers stored with decimal commas.
            if df[column].dtype == "object":
                df[column] = (
                    df[column]
                    .astype(str)
                    .str.strip()
                    .str.replace(",", ".", regex=False)
                )

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # In the original UCI dataset, -200 indicates a missing value.
    df = df.replace(-200, float("nan"))

    # ----------------------------------------------
    # Remove unusable rows
    # ----------------------------------------------

    # Date and Time are required for constructing a timestamp.
    invalid_date_time = df["Date"].isna() | df["Time"].isna()

    removed_date_time = int(invalid_date_time.sum())

    if removed_date_time:
        print(
            f"Removing {removed_date_time:,} rows with invalid "
            "date/time values."
        )

    df = df.loc[~invalid_date_time].copy()

    # ----------------------------------------------
    # Create timestamp
    # ----------------------------------------------

    df["Timestamp"] = pd.to_datetime(
        df["Date"].dt.strftime("%Y-%m-%d")
        + " "
        + df["Time"],
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce"
    )

    df = df.dropna(subset=["Timestamp"]).copy()

    # Keep rows with at least one usable sensor measurement.
    available_measurements = [
        column for column in numeric_columns
        if column in df.columns
    ]

    if available_measurements:
        df = df.dropna(
            subset=available_measurements,
            how="all"
        ).copy()

    # Sort observations chronologically.
    df = df.sort_values("Timestamp").reset_index(drop=True)

    # Put Timestamp first for easier use in later scripts.
    columns = ["Timestamp"] + [
        column for column in df.columns
        if column != "Timestamp"
    ]

    df = df[columns]

    print(f"Rows after cleaning: {len(df):,}")
    print("\nMissing values in key measurements:")

    for column in ["T", "RH", "AH"]:
        if column in df.columns:
            print(f"  {column}: {df[column].isna().sum():,}")

    return df


# --------------------------------------------------
# 4. SAVE CLEANED DATASET
# --------------------------------------------------

def save_dataset(df, path):
    """
    Save cleaned data as a UTF-8 CSV file.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        path,
        index=False,
        encoding="utf-8"
    )

    print(f"\nCleaned dataset saved to:\n{path}")
    print(f"Final row count: {len(df):,}")
    print(f"Final column count: {len(df.columns)}")


# --------------------------------------------------
# 5. MAIN PROGRAM
# --------------------------------------------------

def main():
    print("=" * 60)
    print("AIR QUALITY DATA PREPROCESSING")
    print("=" * 60)

    raw_df = load_dataset(INPUT_FILE)

    cleaned_df = clean_dataset(raw_df)

    save_dataset(cleaned_df, OUTPUT_FILE)

    print("\nPreprocessing completed successfully.")


if __name__ == "__main__":
    main()
