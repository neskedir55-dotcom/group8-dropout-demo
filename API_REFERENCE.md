# API reference

Base URL: `http://localhost:8000`. Interactive reference: `/docs`. OpenAPI: `/openapi.json`.

## Endpoints

| Method | Path | Request | Success |
|---|---|---|---|
| GET | `/health` | None | 200 with `status` and `model_version` |
| POST | `/predict` | One student as a JSON object | 200 with prediction fields below |

Send `Content-Type: application/json`. This API accepts one student per request.

## Input fields

All 28 fields are required. JSON keys match the original model columns exactly, including spaces, punctuation and `Nacionality`. Integer fields accept JSON integers, not strings, booleans or fractional values. Numeric fields accept finite JSON numbers. Nulls and extra fields are rejected. Category codes must come from the saved metadata; do not invent institution-specific mappings.

The ranges below are the **training data ranges**, used as the API's accepted domain. They are not universal limits for student data. All range endpoints are inclusive. Count fields use whole units, and grade is numeric.

| Field (exact JSON key) | Type | Valid values/range | Meaning |
|---|---|---|---|
| `Marital status` | integer enum | 1, 2, 3, 4, 5, 6 | Marital status category code. |
| `Application mode` | integer enum | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18 | Admission application mode category code. |
| `Application order` | integer enum | 0, 1, 2, 3, 4, 5, 6, 9 | Order of preference in the application (coded value). |
| `Course` | integer enum | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 | Degree course category code. |
| `Daytime/evening attendance` | integer enum | 0, 1 | Attendance: 1 daytime, 0 evening. |
| `Previous qualification` | integer enum | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 | Previous qualification category code. |
| `Nacionality` | integer enum | 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 | Nationality category code; original training spelling is required. |
| `Mother's qualification` | integer enum | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29 | Mother qualification category code. |
| `Father's qualification` | integer enum | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34 | Father qualification category code. |
| `Mother's occupation` | integer enum | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32 | Mother occupation category code. |
| `Father's occupation` | integer enum | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 21, 23, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 43, 44, 45, 46 | Father occupation category code. |
| `Displaced` | integer enum | 0, 1 | Displaced student flag: 1 yes, 0 no. |
| `Educational special needs` | integer enum | 0, 1 | Special educational needs flag: 1 yes, 0 no. |
| `Debtor` | integer enum | 0, 1 | Debtor flag: 1 yes, 0 no. |
| `Tuition fees up to date` | integer enum | 0, 1 | Tuition fees current: 1 yes, 0 no. |
| `Gender` | integer enum | 0, 1 | Dataset gender code: 1 male, 0 female. |
| `Scholarship holder` | integer enum | 0, 1 | Scholarship holder flag: 1 yes, 0 no. |
| `Age at enrollment` | integer | 17 to 70 (inclusive) | Age in completed years at enrollment. |
| `International` | integer enum | 0, 1 | International student flag: 1 yes, 0 no. |
| `Curricular units 1st sem (credited)` | integer | 0 to 20 (inclusive) | First semester curricular units: credited. |
| `Curricular units 1st sem (enrolled)` | integer | 0 to 26 (inclusive) | First semester curricular units: enrolled. |
| `Curricular units 1st sem (evaluations)` | integer | 0 to 45 (inclusive) | First semester curricular units: evaluations. |
| `Curricular units 1st sem (approved)` | integer | 0 to 26 (inclusive) | First semester curricular units: approved. |
| `Curricular units 1st sem (grade)` | number | 0 to 18.875 (inclusive) | First semester mean grade on the dataset 0–20 scale. |
| `Curricular units 1st sem (without evaluations)` | integer | 0 to 12 (inclusive) | First semester curricular units: without evaluations. |
| `Unemployment rate` | number | 7.6 to 16.2 (inclusive) | Contextual unemployment rate in percent. |
| `Inflation rate` | number | -0.8 to 3.7 (inclusive) | Contextual inflation rate in percent. |
| `GDP` | number | -4.06 to 3.51 (inclusive) | Contextual GDP growth rate in percent. |

## Response fields

| Field | Type | Range/values | Meaning |
|---|---|---|---|
| `probability` | number | 0 to 1 | Dropout probability, rounded to four decimal places |
| `risk_label` | string | `high_risk`, `low_risk` | High risk when unrounded Dropout probability is at least 0.38 |
| `predicted_outcome` | string | `Dropout`, `Enrolled`, `Graduate` | Threshold decision, then most likely non-Dropout class |
| `probabilities` | object | Three fields below | Probability of each original model class |
| `probabilities.Dropout` | number | 0 to 1 | Dropout probability |
| `probabilities.Enrolled` | number | 0 to 1 | Enrolled probability |
| `probabilities.Graduate` | number | 0 to 1 | Graduate probability |
| `threshold` | number | 0.38 in version 1.0.0 | Saved Module 5 dropout threshold |
| `model_version` | string | `1.0.0` | Version of this API and artifact release (set by the `MODEL_VERSION` setting) |
| `request_id` | string or null | `3f9c1c0e7a5b4d2e8a1b6c9d0e2f4a7b` | Id of this prediction in the monitoring log (6.6). Keep it to attach the real outcome later. `null` only if logging failed. |

All probabilities are rounded independently to four decimal places, so their sum may differ slightly from 1. The risk label uses the unrounded probability; a displayed 0.3800 can therefore be low risk if the raw value is just below 0.38.

Actual successful response for [the example student](examples/valid_student.json):

```json
{
  "probability": 0.4128,
  "risk_label": "high_risk",
  "predicted_outcome": "Dropout",
  "probabilities": {
    "Dropout": 0.4128,
    "Enrolled": 0.5583,
    "Graduate": 0.0289
  },
  "threshold": 0.38,
  "model_version": "1.0.0",
  "request_id": "3f9c1c0e7a5b4d2e8a1b6c9d0e2f4a7b"
}
```

This student is flagged even though Enrolled has the highest individual probability. The saved decision rule deliberately prioritizes Dropout when its probability reaches 0.38.

Health response:

```json
{"status": "healthy", "model_version": "1.0.0"}
```

## Error behavior

| Situation | Behavior | Client action |
|---|---|---|
| Missing field, wrong type, range violation, unknown category, null, extra field or malformed JSON | HTTP 422; `detail` contains the failing field location, error type and message | Correct the JSON and resend |
| Model inference failure or invalid model probabilities | HTTP 500 with exactly `{"detail":"Prediction failed"}` | Check server logs; internal exception is logged on the server |
| Missing/unreadable model, incorrect feature/class metadata | Application startup fails; it does not report a healthy service | Restore matching artifacts and restart |

Invalid requests are rejected before inference. Full live examples appear in [the invalid-input log](evidence/invalid_input_log.md). The test `test_internal_error_returns_safe_message` deliberately injects a model error and verifies that private details do not appear in the HTTP response.

## Limits statement

This is a local educational early-warning service for human review. It does not make admissions, funding, disciplinary, or other automated student decisions. Its three probabilities are model estimates, not guarantees.

The pipeline was trained on 3,539 rows of the original 4,424-student dataset, with 885 held out for testing. It requires information available by the end of the first semester; it cannot serve as a pre-enrollment prediction. It excludes second-semester features. The saved pipeline handles scaling and categorical encoding, with no fitting during API requests.

The saved test metrics at the 0.38 threshold are macro-F1 0.6598, Dropout recall 0.7254 and Dropout precision 0.7715. These are historical Module 5 results from the metadata; the API tests verify serving behavior and do not constitute a fresh model evaluation.

Known limitations from the project: lower Dropout recall for students aged 19 or under, female students and displaced students; missed later Dropouts who had strong first-semester results; and weaker performance for Enrolled. Small subgroups limit conclusions. Age and gender are model inputs. New institutions need a reviewed category mapping and independent validation. Values outside the training domain require review and potential retraining, not removal of validation.

This service accepts one student at a time. Batch prediction remains available in the existing Streamlit app. Authentication, rate limiting and production deployment are outside this lab's scope.
