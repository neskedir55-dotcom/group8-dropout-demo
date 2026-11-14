# Group 8: Build and Test a Prediction API

This lab serves the existing Module 5 student dropout pipeline through FastAPI. It follows the five guided steps in the supplied Sub-module 6.2 screenshots, using student fields instead of the example loan fields. The original Streamlit application remains in `../app.py`.

## Step 1: Set up the project

Open a terminal in `Group_8_Module_5_Project/prediction_api` (the directory containing this README). Use Python 3.12, which was used for verification.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On the current workspace, the prepared environment is also available:

```bash
source ../.venv-linux/bin/activate
```

The files are organized as requested in the lab:

```text
prediction_api/
├── app/
│   ├── config.py                  # Settings read from environment variables (MODEL_PATH, THRESHOLD, MODEL_VERSION)
│   ├── logging_db.py              # 6.6 prediction log (SQLite) and privacy reduction
│   ├── __init__.py
│   ├── main.py                    # Startup loading, /health and /predict
│   └── schemas.py                 # Typed, documented 28-field input and outputs
├── model_artifacts/
│   ├── dropout_risk_model.joblib  # Existing fitted preprocessing + classifier
│   ├── model_metadata.json        # Existing decision rule and validation domain
│   └── README.md                  # Artifact provenance and checksum
├── tests/test_api.py
├── examples/valid_student.json
├── evidence/                      # Actual responses, screenshots and test results
├── requirements.txt
├── requirements-docker.txt         # Pinned runtime packages used inside the container
├── requirements-monitoring.txt     # Extra packages for the 6.6 dashboard and simulation
├── MONITORING.md                   # 6.6 log design, alert policy, privacy, interpretation
├── simulate_logs.py                # 6.6 simulated 21-day history
├── monitoring_core.py              # 6.6 indicators, alerts, charts (shared)
├── monitoring_dashboard.py         # 6.6 optional Streamlit dashboard
├── Dockerfile                     # Container image for the API (listens on $PORT, default 8000)
├── .env.example                   # Setting names only, no secrets
├── DEPLOYMENT.md                  # Cloud deployment plan, platform comparison, cold start, rollback
├── API_REFERENCE.md
└── SUBMISSION.md
```

The saved model already contains preprocessing and Logistic Regression in one scikit-learn Pipeline. `model_artifacts/dropout_risk_model.joblib` is a byte-for-byte copy of `../Models/dropout_risk_model.joblib`; there is no retraining or separate preprocessing at serving time. The library versions match the saved metadata for scikit-learn, pandas, numpy and joblib.

## Step 2: Write the API

Implemented in [app/main.py](app/main.py) and [app/schemas.py](app/schemas.py).

- `GET /health` reports status and model version after successful startup.
- `POST /predict` validates all 28 fields and sends them to the pipeline in training order.
- The fitted pipeline loads once per worker at startup, using paths derived from `__file__`.
- The response includes Dropout probability, risk label, all class probabilities, predicted outcome, threshold and version.
- The original threshold is **0.38**. If Dropout probability is below it, choose the more likely of Enrolled and Graduate.
- Invalid input returns 422. Internal prediction errors return a safe 500 message.

See [API_REFERENCE.md](API_REFERENCE.md) for the full input table, response table, error note and limits statement.

## Step 3: Run the service and try it

From `prediction_api/`, with the environment active:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs**. Expand **POST /predict**, click **Try it out**, keep the supplied example body, and click **Execute**. Expect HTTP 200. `GET /health` can be tried on the same page.

Or use a second terminal from `prediction_api/`:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  --data-binary @examples/valid_student.json
```

The captured sample response has Dropout probability **0.4128**, `high_risk`, and predicted outcome `Dropout`. See [the actual response](evidence/successful_prediction.json), [the docs screenshot](evidence/docs.png), and [the executed prediction screenshot](evidence/successful_prediction.png).

## Step 4: Send invalid requests on purpose

With the service still running, execute:

```bash
python scripts/record_requests.py
```

This script records actual responses for missing `Age at enrollment`, the wrong type `"young"`, out-of-range age `900`, and unknown Course code `999`. All four return HTTP **422**. Read the [invalid-input log](evidence/invalid_input_log.md) for the messages and the [JSON log](evidence/invalid_input_log.json) for every full request and response. The script also saves the live health response, successful prediction and OpenAPI specification.

## Step 5: Write and run automated tests

```bash
python -m pytest tests/ -v
```

**Recorded result: 93 passed** (76 API tests plus 17 logging tests added in 6.6). The test output includes one upstream Starlette deprecation warning about its HTTPX TestClient integration; it does not affect the passing tests.

[Test results](evidence/test_results.txt) and [test source](tests/test_api.py) cover:

| Tests | What they protect against |
|---|---|
| Health and valid prediction | Broken endpoints and changes from the saved pipeline probabilities/decision rule |
| Every required field | Accidentally allowing incomplete student records |
| Wrong type, range, category, null, boolean, extra field and string code | Invalid requests reaching the model |
| Each numeric lower/upper bound | Incorrect acceptance at boundaries or outside the training domain |
| Each category field | Codes unknown to the model |
| Threshold boundary and both non-Dropout outcomes | Replacing 0.38 with argmax or applying the threshold after rounding |
| Internal failure and malformed model probabilities | Exposing internal errors or returning unusable probabilities |
| Load-count test | Reloading the model for each prediction |
| OpenAPI schema and docs | Missing field descriptions or required fields in the interactive API |

## Run in Docker

### Why use a container

The container makes the API easy to share and run on any computer with Docker, without recreating my setup by hand. The image starts from python:3.13-slim and installs the exact versions pinned in requirements-docker.txt, including scikit-learn 1.6.1, pandas 2.2.3, numpy 2.1.3 and joblib 1.6.0. These match the versions the model was trained with, so the saved pipeline loads and predicts identically everywhere. The image also carries the app code and the model_artifacts folder, which holds dropout_risk_model.joblib and model_metadata.json, so nothing needs to be downloaded or copied separately. Anyone can build it and run it with two commands, and it listens on port 8000. It runs as a non-root user and includes a /health check, so problems are easy to spot.

### Build and run

The same API can run in a container. From `prediction_api/`:

```bash
docker build -t dropout-api:1.0 .
docker run -d --name dropout-api -p 8000:8000 dropout-api:1.0
docker ps
```

Then open http://localhost:8000/docs. The image installs `requirements-docker.txt`, copies only `app/` and `model_artifacts/`, runs as a non-root user, and uses `/health` as its container health check. To stop and remove it: `docker rm -f dropout-api`.

To check it from the terminal, run `curl -s -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d @examples/valid_student.json` (wait about 10 seconds after starting). The expected result is Dropout probability 0.4128, `high_risk`.

Evidence of the container running is in `evidence/`: `docker_build_and_run.png` (build, run and `docker ps` in the terminal), `docker_successful_prediction.png` (a successful prediction from inside the container) and `docker_container_logs_1.png` / `docker_container_logs_2.png` (Docker Desktop logs showing repeated `GET /health` 200 responses and `POST /predict` 422 responses for invalid input).

## Monitoring (6.6)

Every `/predict` request is written to a SQLite log (`logs/predictions.db`, path set by `LOG_DB_PATH`): time, reduced inputs, probability, decision, model version, latency and status, including failures. Logging can never break a prediction. The notebook `Group_8_Module_6_6_Production_Monitoring.ipynb` (project folder), `simulate_logs.py`, `monitoring_core.py` and `monitoring_dashboard.py` build the dashboard and alerts. Install their extra packages with `pip install -r requirements-monitoring.txt`. See [MONITORING.md](MONITORING.md) for the log design, alert policy, privacy statement and interpretation.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: app` | Run Uvicorn and pytest from `prediction_api/`, not the parent Streamlit directory. |
| Missing dependency | Activate the environment and install `requirements.txt`. Use Python 3.12. |
| Model file not found | Restore `model_artifacts/dropout_risk_model.joblib` and matching metadata. |
| Every prediction returns 422 | Use the exact JSON keys from `examples/valid_student.json`; all 28 are required. |
| Prediction returns 500 | Check server logs and the saved feature/class order. The client response intentionally stays brief. |
| Address already in use | Stop the other server or choose `--port 8001`; pass `--base-url http://127.0.0.1:8001` to evidence scripts. |
| Browser docs do not render | Swagger UI downloads its browser assets from a CDN and requires network access. The API and `/openapi.json` can still be tested directly. |

## Capture screenshots manually

To document the API using screenshots taken during manual testing:

1. Start the API and open `http://localhost:8000/docs` in your browser.
2. Take a screenshot of the API overview and save it as `evidence/docs.png`.
3. Expand **POST /predict**, click **Try it out**, and execute the valid student example.
4. Take a screenshot showing the request URL, HTTP **200** status and prediction response. Save it as `evidence/successful_prediction.png`.
5. Capture the full expanded operation as `evidence/docs_prediction_full.png` if including that additional image.
6. Change `Age at enrollment` to `900`, execute again and capture the HTTP **422** validation response as additional evidence if desired.

Screenshots should show the actual responses from the running API. No browser automation tool is needed for these steps or to run the application.

## Submission

[SUBMISSION.md](SUBMISSION.md) maps all six expected submission items to their files. This directory contains the model copy and can be submitted independently of the Streamlit project.

Implementation references: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/) and [Pydantic model documentation](https://docs.pydantic.dev/latest/concepts/models/).
