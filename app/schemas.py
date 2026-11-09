"""Typed request/response contracts, using the saved training metadata."""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

API_DIR = Path(__file__).resolve().parent.parent
METADATA = json.loads((API_DIR / "model_artifacts/model_metadata.json").read_text())
MODEL_VERSION = "1.0.0"


class PredictionInput(BaseModel):
    """All 28 end-of-first-semester inputs are required; use original CSV keys."""
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    marital_status: Literal[1, 2, 3, 4, 5, 6] = Field(..., alias='Marital status', description='Marital status category code.')
    application_mode: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18] = Field(..., alias='Application mode', description='Admission application mode category code.')
    application_order: Literal[0, 1, 2, 3, 4, 5, 6, 9] = Field(..., alias='Application order', description='Order of preference in the application (coded value).')
    course: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17] = Field(..., alias='Course', description='Degree course category code.')
    daytime_evening_attendance: Literal[0, 1] = Field(..., alias='Daytime/evening attendance', description='Attendance: 1 daytime, 0 evening.')
    previous_qualification: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17] = Field(..., alias='Previous qualification', description='Previous qualification category code.')
    nacionality: Literal[1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20] = Field(..., alias='Nacionality', description='Nationality category code; original training spelling is required.')
    mother_s_qualification: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29] = Field(..., alias="Mother's qualification", description='Mother qualification category code.')
    father_s_qualification: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34] = Field(..., alias="Father's qualification", description='Father qualification category code.')
    mother_s_occupation: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32] = Field(..., alias="Mother's occupation", description='Mother occupation category code.')
    father_s_occupation: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 21, 23, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 43, 44, 45, 46] = Field(..., alias="Father's occupation", description='Father occupation category code.')
    displaced: Literal[0, 1] = Field(..., alias='Displaced', description='Displaced student flag: 1 yes, 0 no.')
    educational_special_needs: Literal[0, 1] = Field(..., alias='Educational special needs', description='Special educational needs flag: 1 yes, 0 no.')
    debtor: Literal[0, 1] = Field(..., alias='Debtor', description='Debtor flag: 1 yes, 0 no.')
    tuition_fees_up_to_date: Literal[0, 1] = Field(..., alias='Tuition fees up to date', description='Tuition fees current: 1 yes, 0 no.')
    gender: Literal[0, 1] = Field(..., alias='Gender', description='Dataset gender code: 1 male, 0 female.')
    scholarship_holder: Literal[0, 1] = Field(..., alias='Scholarship holder', description='Scholarship holder flag: 1 yes, 0 no.')
    age_at_enrollment: int = Field(..., alias='Age at enrollment', ge=17.0, le=70.0, description='Age in completed years at enrollment.')
    international: Literal[0, 1] = Field(..., alias='International', description='International student flag: 1 yes, 0 no.')
    curricular_units_1st_sem_credited: int = Field(..., alias='Curricular units 1st sem (credited)', ge=0.0, le=20.0, description='First semester curricular units: credited.')
    curricular_units_1st_sem_enrolled: int = Field(..., alias='Curricular units 1st sem (enrolled)', ge=0.0, le=26.0, description='First semester curricular units: enrolled.')
    curricular_units_1st_sem_evaluations: int = Field(..., alias='Curricular units 1st sem (evaluations)', ge=0.0, le=45.0, description='First semester curricular units: evaluations.')
    curricular_units_1st_sem_approved: int = Field(..., alias='Curricular units 1st sem (approved)', ge=0.0, le=26.0, description='First semester curricular units: approved.')
    curricular_units_1st_sem_grade: float = Field(..., alias='Curricular units 1st sem (grade)', ge=0.0, le=18.875, description='First semester mean grade on the dataset 0–20 scale.')
    curricular_units_1st_sem_without_evaluations: int = Field(..., alias='Curricular units 1st sem (without evaluations)', ge=0.0, le=12.0, description='First semester curricular units: without evaluations.')
    unemployment_rate: float = Field(..., alias='Unemployment rate', ge=7.6, le=16.2, description='Contextual unemployment rate in percent.')
    inflation_rate: float = Field(..., alias='Inflation rate', ge=-0.8, le=3.7, description='Contextual inflation rate in percent.')
    gdp: float = Field(..., alias='GDP', ge=-4.06, le=3.51, description='Contextual GDP growth rate in percent.')

    @field_validator("*", mode="before")
    @classmethod
    def reject_booleans_and_noninteger_codes(cls, value, info):
        # Python treats True == 1; categorical codes must still be JSON integers.
        alias = cls.model_fields[info.field_name].alias
        if isinstance(value, bool):
            raise ValueError("A boolean is not a numeric student feature")
        if alias in METADATA["allowed_values"] and type(value) is not int:
            raise ValueError("Category codes must be JSON integers")
        return value


class HealthOutput(BaseModel):
    status: Literal["healthy"]
    model_version: str


class ClassProbabilities(BaseModel):
    Dropout: float = Field(ge=0, le=1)
    Enrolled: float = Field(ge=0, le=1)
    Graduate: float = Field(ge=0, le=1)


class PredictionOutput(BaseModel):
    probability: float = Field(ge=0, le=1, description="Dropout probability.")
    risk_label: Literal["high_risk", "low_risk"]
    predicted_outcome: Literal["Dropout", "Enrolled", "Graduate"]
    probabilities: ClassProbabilities
    threshold: float = Field(ge=0, le=1)
    model_version: str
    request_id: str | None = Field(
        default=None,
        description="Identifier of this prediction in the monitoring log. Keep it to attach the real outcome later.",
    )
