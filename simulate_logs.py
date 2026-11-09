"""
Simulate three weeks of prediction history (Sub-module 6.6, Step 4).

Run once from the prediction_api/ folder:   python simulate_logs.py
To start again:                             delete logs/predictions.db and rerun.

What is simulated and what is real
  * REAL: the model, the probabilities (the saved pipeline scores each student) and the
    outcomes (taken from the dataset). Only the 885 students that Module 5 held out for
    testing are used (the same split: test_size=0.2, random_state=42, stratified), so the
    model has never seen them in training.
  * SIMULATED: the dates, the request volume, the latency and the failures. None of it
    is real traffic. Every row is marked is_simulated = 1.
A change is planted in the last six days (a weaker cohort and more failures) so that the
dashboard has something to find.
"""
import os
import sys
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from app.logging_db import init_db, log_prediction, record_outcome, connect, db_path
from app.schemas import METADATA

DATA = Path(os.getenv("STUDENT_DATA", "../Data/Raw/Stdntdropoutdataset.csv"))
MODEL = Path(__file__).resolve().parent / "model_artifacts" / "dropout_risk_model.joblib"
DAYS = 21                      # at least two weeks of history
MODEL_VERSION = os.getenv("MODEL_VERSION", "1.0.0")
THRESHOLD = float(METADATA["dropout_threshold"])

if not DATA.exists():
    sys.exit(f"Dataset not found at {DATA}. Set STUDENT_DATA to the path of Stdntdropoutdataset.csv.")

random.seed(42)
rng = np.random.default_rng(42)
init_db()

with connect() as conn:
    if conn.execute("SELECT COUNT(*) FROM predictions WHERE is_simulated = 1").fetchone()[0]:
        sys.exit(f"{db_path()} already contains simulated rows. Delete the file to start again.")

# --- the held-out students of Module 5, scored by the real model -------------------------
features = METADATA["feature_order"]
data = pd.read_csv(DATA, encoding="utf-8-sig")
_, test = train_test_split(data, test_size=0.2, random_state=42, stratify=data["Target"])
model = joblib.load(MODEL)
dropout_col = list(model.classes_).index("Dropout")
probabilities = model.predict_proba(test[features])[:, dropout_col]
actual = (test["Target"] == "Dropout").astype(int).to_numpy()
rows = test[features].to_dict("records")
approved = test["Curricular units 1st sem (approved)"].to_numpy()
enrolled = test["Curricular units 1st sem (enrolled)"].to_numpy()
ratio = np.divide(approved, enrolled, out=np.ones(len(test)), where=enrolled > 0)
weak_cohort = ratio < 0.5      # students who passed under half of their courses


def native(record):
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in record.items()}


now = datetime.now(timezone.utc)
counts = {"requests": 0, "failures": 0, "outcomes": 0}

for days_ago in range(DAYS, -1, -1):
    day = now - timedelta(days=days_ago)
    recent = days_ago <= 6     # the planted change
    weights = np.where(weak_cohort, 3.0, 1.0) if recent else np.ones(len(test))
    weights = weights / weights.sum()
    for _ in range(random.randint(40, 80)):
        i = int(rng.choice(len(test), p=weights))
        ts = day.replace(hour=random.randint(6, 20), minute=random.randint(0, 59),
                         second=random.randint(0, 59), microsecond=0)
        ts = min(ts, now)      # no timestamps in the future
        latency = max(20.0, random.gauss(120, 25))
        if random.random() < 0.05:                 # occasional slow request
            latency = random.uniform(800, 2000)
        counts["requests"] += 1
        if random.random() < (0.04 if recent else 0.008):   # failed prediction
            log_prediction(native(rows[i]), None, None, MODEL_VERSION, round(latency, 1),
                           status_code=500, timestamp=ts, is_simulated=1)
            counts["failures"] += 1
            continue
        p = float(probabilities[i])
        request_id = log_prediction(native(rows[i]), round(p, 4),
                                    "high_risk" if p >= THRESHOLD else "low_risk",
                                    MODEL_VERSION, round(latency, 1), timestamp=ts, is_simulated=1)
        # Outcomes arrive late: known only for requests older than 10 days (90% coverage)
        if days_ago > 10 and random.random() < 0.9:
            record_outcome(request_id, int(actual[i]))
            counts["outcomes"] += 1

print(f"Simulated logs written to {db_path()}: {counts['requests']} requests, "
      f"{counts['failures']} failures, {counts['outcomes']} known outcomes.")
print("These rows are marked is_simulated = 1.")
