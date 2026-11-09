"""
Settings read from environment variables (Module 6.4: Cloud Deployment).

Anything that can differ between my laptop and the cloud platform lives here, not
in the code. Every setting has a safe default, so the API still starts locally with
no variables set. No secret is stored in this file.

    MODEL_PATH   path to the saved pipeline (relative paths start at prediction_api/)
    THRESHOLD    Dropout decision threshold between 0 and 1
                 (default: the value saved in model_artifacts/model_metadata.json)
    MODEL_VERSION  label written to every response and every log row (default 1.0.0)
    LOG_DB_PATH  prediction log file (read by app/logging_db.py; default logs/predictions.db)
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.schemas import METADATA, MODEL_VERSION

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = "model_artifacts/dropout_risk_model.joblib"


@dataclass(frozen=True)
class Settings:
    model_path: Path
    threshold: float
    model_version: str


@lru_cache
def get_settings() -> Settings:
    model_path = Path(os.getenv("MODEL_PATH") or DEFAULT_MODEL_PATH)
    if not model_path.is_absolute():
        model_path = BASE_DIR / model_path

    raw_threshold = os.getenv("THRESHOLD") or METADATA["dropout_threshold"]
    try:
        threshold = float(raw_threshold)
    except ValueError as error:
        raise RuntimeError(f"THRESHOLD must be a number, got {raw_threshold!r}") from error
    if not 0 <= threshold <= 1:
        raise RuntimeError(f"THRESHOLD must be between 0 and 1, got {threshold}")

    return Settings(model_path=model_path, threshold=threshold,
                    model_version=os.getenv("MODEL_VERSION") or MODEL_VERSION)
