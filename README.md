
# Dynamic, Exposed-Only Safety Layer

## 1. Project Overview

The Dynamic, Exposed-Only Safety Layer is a software-based safety monitoring system that identifies unusual environmental conditions and simulated security events.

The system uses simulated IoT readings, a real environmental dataset, machine learning, rule-based risk assessment, cryptographic authentication, a cloud-style API, and a MySQL database.

The main design principle is data minimization: raw sensor readings and machine-learning processing remain on the local device simulator, while the backend receives only authenticated alert metadata.

No physical IoT hardware is required.

## 2. Objectives

- Simulate IoT environmental and security-related readings.
- Detect unusual environmental measurements using machine learning.
- Identify simulated security events using a rule-based risk engine.
- Generate authenticated alert tokens using HMAC-SHA256.
- Validate alerts through a FastAPI backend.
- Store alert metadata in MySQL.
- Display received alerts through a Streamlit dashboard.
- Minimize the amount of information transmitted to the backend.

## 3. Technologies Used

- Python
- Pandas and NumPy
- Scikit-learn
- Isolation Forest
- FastAPI
- SQLAlchemy
- MySQL
- PyMySQL
- HMAC-SHA256
- Streamlit
- Requests
- Unittest

## 4. Project Structure

```text
exposed_safety_layer/
├── data/
│   ├── raw/
│   │   └── AirQualityUCI.csv
│   ├── processed/
│   └── simulated/
├── device/
│   ├── simulator.py
│   ├── risk_engine.py
│   └── security.py
├── preprocessing/
│   └── prepare_data.py
├── ml/
│   ├── train_model.py
│   ├── evaluate_model.py
│   └── artifacts/
├── backend/
│   ├── cloud_api.py
│   ├── database.py
│   └── models.py
├── tests/
│   ├── __init__.py
│   └── test_security.py
├── dashboard.py
├── requirements.txt
└── README.md
```

## 5. System Architecture

```text
                LOCAL DEVICE SIMULATOR
                ┌────────────────────┐
                │ Simulated Readings │
                └─────────┬──────────┘
                          │
                 ┌────────▼─────────┐
                 │ Rule-Based Risk  │
                 │ Engine           │
                 └────────┬─────────┘
                          │
                ┌─────────▼──────────┐
                │ HMAC-SHA256 Token  │
                │ Generation         │
                └─────────┬──────────┘
                          │
                 Alert Metadata Only
                          │
                ┌─────────▼──────────┐
                │ FastAPI Backend    │
                │ Token Verification │
                └─────────┬──────────┘
                          │
                ┌─────────▼──────────┐
                │ MySQL Database     │
                │ Alert Metadata     │
                └─────────┬──────────┘
                          │
                ┌─────────▼──────────┐
                │ Streamlit Dashboard│
                └────────────────────┘
```

The machine-learning pipeline is separate:

```text
UCI Air Quality Dataset
          |
          v
Data Preprocessing
          |
          v
Isolation Forest Training
          |
          v
Environmental Anomaly Scores
          |
          v
Evaluation Results
```

The UCI dataset supports environmental anomaly detection. It does not contain labels for intrusion or malicious behavior, so it is not used as a labeled intrusion-detection dataset.

## 6. Dataset

Dataset: UCI Air Quality

Official source:
https://archive.ics.uci.edu/dataset/360/air+quality

Download the dataset and place its CSV file at:

`data/raw/AirQualityUCI.csv`

The preprocessing script expects the original semicolon-separated CSV format with comma decimal separators.

Important fields include:

- CO(GT): carbon monoxide reference measurement
- NOx(GT): nitrogen oxides reference measurement
- NO2(GT): nitrogen dioxide reference measurement
- T: temperature
- RH: relative humidity
- AH: absolute humidity

The original dataset uses `-200` to indicate missing measurements. The preprocessing script converts these values to missing values before model training.

## 7. Installation

### Step 1: Install Python

Install a compatible Python version and verify it:

```powershell
python --version
```

### Step 2: Create a virtual environment

```powershell
python -m venv .venv
```

Activate it in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies

```powershell
python -m pip install -r requirements.txt
```

## 8. Configure MySQL

Ensure the MySQL server is running.

Create the project database:

```sql
CREATE DATABASE exposed_safety_db;
```

Configure the database connection in PowerShell:

```powershell
$env:DB_USER = "root"
$env:DB_PASSWORD = "your_mysql_password"
$env:DB_HOST = "localhost"
$env:DB_PORT = "3306"
$env:DB_NAME = "exposed_safety_db"
```

Replace the example password with your actual MySQL password.

The backend creates the `alerts` table automatically when it starts.

## 9. Configure the Device Secret

Generate a random secret in PowerShell:

```powershell
$env:DEVICE_SECRET = [Convert]::ToBase64String(
    [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
)
```

Use the same secret in the simulator and backend terminals.

The secret is used to create and verify HMAC-SHA256 signatures. Keep it private and do not commit it to source control.

## 10. Prepare the Environmental Dataset

Run from the project root:

```powershell
python preprocessing/prepare_data.py
```

The cleaned dataset is saved to:

`data/processed/air_quality_clean.csv`

## 11. Train the Machine-Learning Model

```powershell
python ml/train_model.py
```

The Isolation Forest model is saved under:

`ml/artifacts/`

The model learns patterns in historical environmental measurements and flags observations that appear unusual.

The configured contamination rate is an estimate of the proportion of anomalies expected in the data. It is not a measured real-world anomaly rate.

## 12. Evaluate the Model

```powershell
python ml/evaluate_model.py
```

The evaluation output is saved to:

`data/processed/evaluation_results.csv`

Because the dataset does not provide ground-truth anomaly labels, the script reports detected anomalies and anomaly scores rather than claiming supervised classification accuracy.

## 13. Run the Backend

From the project root:

```powershell
uvicorn backend.cloud_api:app --reload
```

Useful endpoints:

- `GET /` — API status
- `GET /health` — health check
- `POST /alerts` — validate and store an alert
- `GET /alerts` — retrieve recent alert metadata

Interactive API documentation:

http://127.0.0.1:8000/docs

## 14. Run the Simulator

Open another terminal and activate the same virtual environment.

Configure the same `DEVICE_SECRET` in that terminal.

### Safe scenario

```powershell
python device/simulator.py --scenario safe
```

### Suspicious scenario

```powershell
python device/simulator.py --scenario suspicious
```

### Random scenarios

```powershell
python device/simulator.py --scenario random --count 20
```

### Send an alert to the backend

```powershell
python device/simulator.py --scenario suspicious --send-url http://127.0.0.1:8000/alerts
```

A suspicious event that meets the configured alert threshold should generate a signed token and submit it to the API.

## 15. Run the Dashboard

Open another terminal:

```powershell
streamlit run dashboard.py
```

Open the local URL printed by Streamlit, usually:

http://localhost:8501

The dashboard shows:

- Total recent alerts
- High-, medium-, and low-risk counts
- Alerts grouped by event type
- Recent alert history
- Risk-level filtering

The dashboard reads metadata from the backend API and does not query MySQL directly.

## 16. Run Security Tests

From the project root:

```powershell
python -m unittest tests.test_security -v
```

The tests cover:

- Valid token verification
- Token tampering
- Incorrect secrets
- Expired tokens
- Malformed tokens

These are unit tests for the token security functions, not a complete penetration or security test.

## 17. Risk Assessment

The rule-based engine evaluates simulated readings such as:

- Unexpected door opening
- Noise level
- Light level
- Number of nearby devices

It calculates a risk score and assigns a risk level according to the configured rules.

The environmental machine-learning model independently identifies unusual air-quality patterns.

These outputs represent different kinds of events and should not be treated as interchangeable.

## 18. Security and Privacy

- Raw sensor readings remain in the local simulator.
- The backend receives alert metadata rather than the full sensor record.
- HMAC-SHA256 helps the backend verify that a token was created using the shared secret.
- Token expiration limits the acceptance period.
- Unique event IDs prevent duplicate alert records.
- Database credentials and secrets should be stored in environment variables.

HMAC provides authentication and integrity, not encryption. Use HTTPS outside localhost.

For production use, implement device-specific secrets, API access controls, rate limiting, robust replay prevention, secret rotation, and secure key storage.

## 19. Limitations

- Sensor values are simulated; no physical IoT devices are connected.
- The environmental dataset is historical and does not represent every deployment environment.
- Unsupervised anomaly detection can produce false positives and false negatives.
- The air-quality dataset does not label intrusions or malicious activity.
- The rule-based thresholds are demonstration settings and require calibration for real applications.
- The demonstration dashboard and API require additional access controls before public deployment.

## 20. Conclusion

The Dynamic, Exposed-Only Safety Layer demonstrates how local risk assessment, environmental anomaly detection, cryptographic alert authentication, a backend API, and database storage can work together in a software-only IoT security prototype.

By transmitting only authenticated alert metadata, the architecture demonstrates a data-minimization approach while separating environmental anomaly detection from simulated security-event detection.
```

## 3. Final run order

Once all files are saved, use this sequence from the project root:

1. Install packages: `python -m pip install -r requirements.txt`
2. Create the MySQL database and configure environment variables.
3. Set `DEVICE_SECRET` in the backend and simulator terminals.
4. Prepare the dataset: `python preprocessing/prepare_data.py`
5. Train the model: `python ml/train_model.py`
6. Evaluate it: `python ml/evaluate_model.py`
7. Start the backend: `uvicorn backend.cloud_api:app --reload`
8. Start the dashboard: `streamlit run dashboard.py`
9. Send a simulated alert and verify it appears on the dashboard.
10. Run the tests: `python -m unittest tests.test_security -v`

**Before your first full run:** ensure the `device/`, `backend/`, `tests/`, `preprocessing/`, and `ml/` directories are importable packages where needed. Adding empty `__init__.py` files to these folders is a safe option, particularly for the relative imports in `backend/models.py`.