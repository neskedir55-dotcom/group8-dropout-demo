"""
Prediction log (Sub-module 6.6: Production Monitoring).

One SQLite row per /predict request, including failures. Logging is deliberately
separate from prediction: `safe_log` never raises, so a logging problem can never
break a prediction.

Privacy by design: `minimise` is the single place where the 28 model inputs are
reduced to the fields monitoring needs. Every write goes through it, so the sensitive
fields cannot be stored by accident.

The log path comes from the LOG_DB_PATH environment variable (default logs/predictions.db)
and is read at call time, so tests and notebooks can point it somewhere else.
"""
import json
import logging
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "logs/predictions.db"

# Fields kept in the log: enough to explain a change in the scores.
LOGGED_FIELDS = [
    "Course",
    "Application mode",
    "Daytime/evening attendance",
    "Tuition fees up to date",
    "Scholarship holder",
    "Curricular units 1st sem (credited)",
    "Curricular units 1st sem (enrolled)",
    "Curricular units 1st sem (evaluations)",
    "Curricular units 1st sem (approved)",
    "Curricular units 1st sem (grade)",
    "Curricular units 1st sem (without evaluations)",
    "Unemployment rate",
    "Inflation rate",
    "GDP",
]
# Deliberately NOT logged (personal, sensitive or family background, and not needed
# for monitoring): Marital status, Application order, Previous qualification,
# Nacionality, Mother's / Father's qualification and occupation, Displaced,
# Educational special needs, Debtor, Gender, International, and the exact age
# (only an age band is kept).

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    input_features TEXT NOT NULL,
    probability REAL,
    decision TEXT,
    model_version TEXT NOT NULL,
    latency_ms REAL,
    status_code INTEGER NOT NULL DEFAULT 200,
    is_simulated INTEGER NOT NULL DEFAULT 0,
    actual_outcome INTEGER
);
CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions (timestamp);
"""


def db_path() -> str:
    return os.getenv("LOG_DB_PATH", DEFAULT_DB_PATH)


def connect():
    # timeout: if two processes write at the same moment, wait instead of failing at once
    return sqlite3.connect(db_path(), timeout=10)


def init_db():
    """Create the logs folder and the table if they do not exist."""
    folder = os.path.dirname(db_path())
    if folder:
        os.makedirs(folder, exist_ok=True)
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)


def age_band(age) -> str:
    """Replace an exact age with a band (less identifying)."""
    try:
        age = float(age)
    except (TypeError, ValueError):
        return "unknown"
    if age < 20:
        return "under 20"
    if age < 25:
        return "20-24"
    if age < 35:
        return "25-34"
    return "35 and over"


def minimise(features: dict) -> dict:
    """Keep only the fields monitoring needs; turn the exact age into a band."""
    kept = {name: features[name] for name in LOGGED_FIELDS if name in features}
    if "Age at enrollment" in features:
        kept["Age band"] = age_band(features["Age at enrollment"])
    return kept


def log_prediction(features, probability, decision, model_version, latency_ms,
                   status_code=200, timestamp=None, is_simulated=0):
    """Write one row and return its request_id."""
    request_id = uuid.uuid4().hex
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    with closing(connect()) as conn, conn:  # 'with conn' commits the change
        conn.execute(
            "INSERT INTO predictions (request_id, timestamp, input_features, probability,"
            " decision, model_version, latency_ms, status_code, is_simulated)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (request_id, timestamp.isoformat(timespec="seconds"),
             json.dumps(minimise(features)), probability, decision, model_version,
             latency_ms, status_code, is_simulated),
        )
    return request_id


def safe_log(*args, **kwargs):
    """Like log_prediction, but a logging failure never reaches the caller."""
    try:
        return log_prediction(*args, **kwargs)
    except Exception:
        logger.exception("Could not write the prediction log")
        return None


def record_outcome(request_id, outcome):
    """Store the real outcome (1 = dropped out, 0 = did not). Returns rows updated."""
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "UPDATE predictions SET actual_outcome = ? WHERE request_id = ?",
            (int(outcome), request_id),
        )
        return cur.rowcount
