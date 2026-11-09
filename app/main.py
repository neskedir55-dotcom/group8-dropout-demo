"""
Student Dropout Early-Warning API  (Module 6.2: Model Serving with FastAPI)

Run from the prediction_api/ folder (the one that contains app/):
    python -m uvicorn app.main:app --port 8000
Then open http://localhost:8000/docs

The request and response contracts live in app/schemas.py. The saved model is the
complete fitted Module 5 pipeline (preprocessing + Logistic Regression); nothing is
retrained or re-implemented here.
"""
import logging
import math
import time
from contextlib import asynccontextmanager

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException

from app.config import get_settings
from app.logging_db import init_db, safe_log
from app.schemas import (
    METADATA,
    HealthOutput,
    PredictionInput,
    PredictionOutput,
)

logger = logging.getLogger("dropout_api")
logging.basicConfig(level=logging.INFO)

# Settings come from environment variables (see app/config.py). Without any variables
# they equal the Module 5 values: the saved model file and the 0.38 threshold.
settings = get_settings()
MODEL_PATH = settings.model_path
THRESHOLD = settings.threshold
MODEL_VERSION = settings.model_version
CLASSES = list(METADATA["classes"])                # ["Dropout", "Enrolled", "Graduate"]
FEATURE_ORDER = list(METADATA["feature_order"])    # the 28 training columns, in order


def check_startup_consistency(model) -> None:
    """Fail at startup (not at the first request) if code and model disagree."""
    schema_columns = {field.alias for field in PredictionInput.model_fields.values()}
    if schema_columns != set(FEATURE_ORDER):
        raise RuntimeError("Input schema fields do not match the training feature list.")
    if list(model.classes_) != CLASSES:
        raise RuntimeError("Class order in the model differs from the metadata file.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the fitted pipeline ONCE per startup, not once per request."""
    model = joblib.load(MODEL_PATH)
    check_startup_consistency(model)
    app.state.model = model
    try:
        init_db()  # create the monitoring log table; the API still starts if this fails
    except Exception:
        logger.exception("Could not create the prediction log; predictions will not be logged")
    logger.info("Model loaded from %s (version %s)", MODEL_PATH.name, MODEL_VERSION)
    yield


app = FastAPI(
    title="Student Dropout Early-Warning API",
    description=(
        "Estimates Dropout / Enrolled / Graduate probabilities from first-semester "
        "information. A support tool for human review, not an automated decision."
    ),
    version=MODEL_VERSION,
    lifespan=lifespan,
)


def clean_probabilities(raw, classes) -> dict[str, float]:
    """Return {class: probability} or raise ValueError if the model output is unusable."""
    values = [float(v) for v in raw[0]]
    if len(values) != len(CLASSES) or len(list(classes)) != len(CLASSES):
        raise ValueError("Unexpected number of class probabilities")
    if any(not math.isfinite(v) or v < 0 or v > 1 for v in values):
        raise ValueError("Probabilities must be finite and between 0 and 1")
    if abs(sum(values) - 1.0) > 1e-3:
        raise ValueError("Probabilities must sum to 1")
    return dict(zip([str(c) for c in classes], values))


def decide(probabilities: dict[str, float]) -> str:
    """Module 5 decision rule: flag Dropout if P(Dropout) >= threshold, otherwise
    choose the more likely of Enrolled and Graduate."""
    if probabilities["Dropout"] >= THRESHOLD:
        return "Dropout"
    return "Enrolled" if probabilities["Enrolled"] >= probabilities["Graduate"] else "Graduate"


@app.get("/health", response_model=HealthOutput)
def health():
    return {"status": "healthy", "model_version": MODEL_VERSION}


@app.post("/predict", response_model=PredictionOutput)
def predict(item: PredictionInput):
    # Original training column names, in the original training order.
    row = item.model_dump(by_alias=True)
    start = time.perf_counter()
    try:
        model = app.state.model
        frame = pd.DataFrame([row], columns=FEATURE_ORDER)
        probabilities = clean_probabilities(model.predict_proba(frame), model.classes_)
        outcome = decide(probabilities)
    except Exception:
        logger.exception("Prediction failed")  # full details stay in the server log
        latency_ms = (time.perf_counter() - start) * 1000
        # Log the failure too, so the error rate can be measured (never raises).
        safe_log(row, None, None, MODEL_VERSION, latency_ms, status_code=500)
        raise HTTPException(status_code=500, detail="Prediction failed")  # safe client message

    latency_ms = (time.perf_counter() - start) * 1000
    rounded = {name: round(value, 4) for name, value in probabilities.items()}
    risk_label = "high_risk" if outcome == "Dropout" else "low_risk"
    # Logging happens after the result is known and outside the inference code,
    # so it can never decide or break the prediction.
    request_id = safe_log(row, rounded["Dropout"], risk_label, MODEL_VERSION, round(latency_ms, 1))
    return PredictionOutput(
        probability=rounded["Dropout"],
        risk_label=risk_label,
        predicted_outcome=outcome,
        probabilities=rounded,
        threshold=THRESHOLD,
        model_version=MODEL_VERSION,
        request_id=request_id,
    )
