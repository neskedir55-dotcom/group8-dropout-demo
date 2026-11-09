# Sub-module 6.6: Production Monitoring (Group 8)

Everything below was produced by the notebook `Group_8_Module_6_6_Production_Monitoring.ipynb` (in the project folder, next to `prediction_api/`) running our real API, our saved Module 5 model and the student-dropout dataset.

| Submission item | Where |
|---|---|
| 1. Log design: schema, logging code, sample records | Section 1 below, `app/logging_db.py`, `app/main.py`, `evidence/log_sample.csv` |
| 2. Dashboard evidence: screenshots, at least four panels | `evidence/monitoring_dashboard.png` (six panels), the notebook (interactive charts), `monitoring_dashboard.py` (optional Streamlit version) |
| 3. Alert policy | Section 3 |
| 4. Interpretation note | Section 4 |
| 5. Privacy statement | Section 5 |
| 6. Data statement | Section 6 |

## 6.6 Data statement (what is simulated)

- **Simulated (`is_simulated = 1`):** about 1,400 requests over 21 days. The **dates, request volume, latency and failures are invented**, and a change was planted in the last six days (a weaker cohort of students and more failures) so the dashboard has something to find.
- **Real inside the simulation:** the probabilities come from our real model and the outcomes from the dataset, using only the 885 students Module 5 held out for testing (same split, `random_state=42`, stratified), so the model never saw them in training.
- **Real API calls (`is_simulated = 0`):** 20 requests sent to a copy of our API running in the notebook (Step 3), using students from that same test set. They are not real new applicants.
- **No real production traffic is included.** The deployed Render service (6.4) keeps its own log on temporary storage that the dashboard cannot read, so, as the lab says, the dashboard uses simulated history.
- The dashboard prints a warning whenever simulated rows are present, and the screenshot title says "SIMULATED data".

## 1. Log design

**Schema** (`app/logging_db.py`, SQLite table `predictions`, one row per `/predict` request including failures):

| Column | Type | Purpose |
|---|---|---|
| `id` | INTEGER, primary key | Row number |
| `request_id` | TEXT, unique, not null | Random id, returned in the response, used to attach the real outcome later |
| `timestamp` | TEXT, not null | UTC, one fixed ISO format so it sorts as text |
| `input_features` | TEXT (JSON), not null | The model inputs, **reduced** (see below) |
| `probability` | REAL | Probability of Dropout; empty for failed requests |
| `decision` | TEXT | `high_risk` or `low_risk` (threshold 0.38); empty for failed requests |
| `model_version` | TEXT, not null | Release that produced the prediction (from the `MODEL_VERSION` setting) |
| `latency_ms` | REAL | Time to produce the prediction |
| `status_code` | INTEGER, not null | 200 success, 500 failure inside the service |
| `is_simulated` | INTEGER, not null | 1 simulated, 0 real |
| `actual_outcome` | INTEGER | 1 dropped out, 0 did not; empty until known |

**What is kept and what is not.** The log keeps 14 of the 28 model inputs that explain the score (course, application mode, evening attendance, tuition up to date, scholarship, the six semester-1 course figures, unemployment, inflation, GDP) plus an **age band** instead of the exact age. It never stores marital status, application order, previous qualification, nationality, the parents' qualification and occupation, displaced, educational special needs, debtor, gender, international, or the exact age. These are personal or sensitive and monitoring does not need them. No names or student ids exist anywhere in the system. One function, `minimise`, applies this reduction to every write, and a test (`test_sensitive_fields_are_never_stored`) fails if a sensitive field is ever stored.

**Logging in the API.** `/predict` writes the log row after the result is known and outside the inference code, through `safe_log`, which catches every logging error, so logging cannot change or break a prediction. Failures are logged with status 500 (probability and decision empty), so the error rate is measurable. Invalid requests (HTTP 422) are rejected before reaching the model and are not logged. If the log cannot be created, the API still starts. The response now has an optional `request_id` field; the 6.5 demo ignores it, so it keeps working. Settings come from environment variables (`MODEL_VERSION`, `LOG_DB_PATH`).

**Sample records:** `evidence/log_sample.csv` (20 real test calls, 12 simulated successes, 3 simulated failures; the `is_simulated` column tells them apart).

**Tests (17 new, 93 in total, all passing):** success is logged with every column; failures are logged with status 500 and the caller gets only a safe message; a broken log path cannot break a prediction or stop the API starting; invalid input is not logged; sensitive fields are never stored; age bands; outcomes are joined by `request_id`; ids are unique; the model version comes from the environment. Output: `evidence/test_results.txt`.

## 2. Dashboard

`monitoring_core.py` holds the indicators, alert rules and charts once, and the notebook and the optional Streamlit app (`monitoring_dashboard.py`, tested with Streamlit's test runner, no errors) both use it.

- **Indicators (6):** requests, error rate, high-risk flag rate, average dropout probability, average latency, 95th percentile latency.
- **Charts (6):** requests per day, distribution of predicted probabilities, daily flag rate, latency per day (mean and 95th percentile), daily error rate, predicted vs actual dropout rate.
- **Alert panel** and **performance on known outcomes** (precision and recall against the Module 5 test results).

Screenshot: `evidence/monitoring_dashboard.png`. It is drawn with matplotlib from the same data, because exporting the interactive Plotly charts as images needs a browser that was not available; the interactive charts are in the notebook outputs.

## 3. Alert policy

| # | Indicator | Condition | Level | Owner | Action |
|---|---|---|---|---|---|
| 1 | Error rate | above 2% of requests in the last 7 days | **High** | Developer on duty | Read the service log, find the cause, consider a rollback to the last good version (6.4 rollback plan, `DEPLOYMENT.md`). |
| 2 | Average latency | more than twice the earlier level | Medium | Developer on duty | Check load, recent releases and whether the service was waking from sleep (cold start measured at 31.6 s). |
| 3 | High-risk flag rate | shifts by more than 10 percentage points | Medium | Model owner | Investigate the inputs, the data pipeline and any change in the cohort or policy. |
| 4 | Average dropout probability | shifts by more than 0.08 | Medium | Model owner | Compare score histograms with earlier weeks; check the model version. |
| 5 | Logging gap | no records for 24 hours | Info | Developer on duty | Check the service and logging are running and the log file is writable. |
| 6 | Dropout recall (30+ known outcomes) | more than 10 points below the Module 5 test result (72.5%) | **High** | Model owner | Review recent errors with advisers; plan a retraining review. |

Rules compare the last 7 days with the period before and refuse to compare when either has fewer than 30 records. The thresholds are starting points, to be revised when we learn what normal variation looks like. The owners are roles; the group should name the people (suggestion: developer on duty = the person who deployed the service; model owner = the person who trained the model).

## 4. Interpretation note

On this run the alert panel showed one High alert (error rate) and two Medium alerts (flag rate, average probability); latency raised none.

**What changed.** Three things moved at the same time, starting around 2 November: the **error rate** rose from about 1% to about 4% of requests (alert, High); the **high-risk flag rate** rose from about 30% to about 45% (+15.8 points, alert, Medium); and the **average dropout probability** rose from about 30% to about 44% (+0.141, alert, Medium). The score histogram has more mass on the right. **Latency did not change** (average about 190 ms before, about 175 ms now), and no latency alert fired.

**What might explain it.** (1) A different group of students is being scored, for example a new intake with weaker first-semester results. (2) A fault in the data pipeline that feeds the model (wrong or missing values), which would also explain the failed requests. (3) A change of model or threshold. (4) A quiet week with too few requests, so the rates are just noise.

**What we checked.** *Volume:* about 60 requests a day before and 64 in the last 7 days, and both periods have far more than the 30 records the alert panel requires, so noise is not the explanation. *Model version:* only 1.0.0 appears in the log, so no release or threshold change coincides with the shift. *Inputs:* the share of requests from students who passed fewer than half of their enrolled courses rose from about 19% to about 42%, so the scored population really did change, which explains a higher flag rate without any fault in the model. *Errors:* they rose at the same time as the shift, so a pipeline problem cannot be ruled out and the failed requests need a look in the service log. *Real outcomes:* outcomes are known only for requests older than 10 days, so none exist yet for the changed week. On the earlier period the model still behaves as in Module 5: precision about 76% (Module 5: 77%), recall about 68% (Module 5: 72.5%, within our 10-point tolerance), and predicted dropout rate 30% against an actual 33%.

**What we decided.** Do not retrain or change the threshold yet, because the evidence points to a changed cohort, not a broken model. The developer on duty reads the service log for the failed requests (rule 1, High). The model owner asks the registrar whether a new intake or programme explains the weaker results, and compares the input fields with the earlier weeks. Advisers keep reviewing every flag; a higher flag rate means more students to support, which is the system working as intended if the cohort really is weaker. We repeat this review when outcomes for the changed week arrive (about 10 days later) and retrain only if recall falls more than 10 points below the Module 5 result.


## 5. Privacy statement

**What we log:** for each prediction, a random request id, the UTC time, the probability and risk label, the model version, the latency, the status code, whether the row is simulated, and later the real outcome. Of the model inputs we store only 14 academic, course and economic-context fields and an age band. **What we chose not to record:** names or any student identifier, gender, nationality, marital status, family background (parents' qualification and occupation), displaced status, special educational needs, debtor status, international status, previous qualification, application order and the exact age. **Why:** the log exists to detect changes in the model and the service; it does not need to know who a student is, and sensitive attributes would turn a monitoring log into a privacy risk. **How it is protected:** the log is a local SQLite file (`logs/predictions.db`), excluded from Git (`.gitignore`) and from the Docker image (`.dockerignore`), readable only by the developer team that runs the service, and tested so that sensitive fields cannot be stored. **Retention:** records should be kept for at most one academic year and then deleted (to be confirmed by the institution). The log produced for this submission contains only simulated rows and 20 test requests, so it holds no real student data.

**Limits.** The reduced inputs can still be personal in combination (for example a rare course with an unusual age band). Free cloud services erase local files on restart, so a production deployment would need a managed database with access control (an extension, not part of this sub-module). Monitoring fairness across groups, for example by gender, would need the sensitive fields we leave out, which is a separate decision for the institution.

## Review questions

1. **Operational vs model monitoring.** Operational monitoring asks whether the service is running, fast and free of errors (requests, latency, error rate). Model monitoring asks whether the predictions still look sensible and, when outcomes arrive, whether they are still correct (score distribution, flag rate, real precision and recall). The first tells you the system is up; the second tells you it is still right.
2. **Why the score distribution matters before outcomes arrive.** Our outcomes take about a term to appear. Until then, a shift in the predicted probabilities is the earliest evidence that the inputs or the model have changed. In our simulation the average probability rose from about 30% to about 44% a week before any outcome could confirm a problem.
3. **A rate drops from 60% to 40% in one week (the lab's approval-rate example).** (a) The population changed: compare the input distributions with earlier weeks (we did this with the share of weak first-semester results). (b) The data pipeline broke and sends wrong or missing values: look at the error rate and at odd or extreme input values. (c) The model or threshold changed: check the `model_version` column and the `THRESHOLD` setting. (d) The week simply had few requests: check the request counts before concluding anything.
4. **Why a logging failure must never stop a prediction.** Monitoring is secondary to the service. A full disk or a locked database would otherwise become an outage for the users. `safe_log` catches every logging error, and `test_logging_failure_never_breaks_a_prediction` proves it.
5. **Why every record has the model version.** To link a change in behaviour to a release, to compare versions, and to know which version to roll back to.
6. **Outcomes known only for part of the population.** Any measurement describes only that part, so it can be biased and must not be generalised, and precision or recall may not even be computable. In our domain the outcome is eventually known for every student, but flagged students receive support, which can change what happens to them, so the outcomes are not a clean test of the model alone. Few known outcomes also make the figures unstable, so the count is always shown next to the result.

## Check before you submit

- [x] Every logged record includes the model version (column is `NOT NULL`; `test_successful_prediction_is_logged`).
- [x] A logging failure cannot break a prediction (`test_logging_failure_never_breaks_a_prediction`).
- [x] Simulated data is labelled as simulated, in the data (`is_simulated`), in the notebook warning, in the screenshot title and in the data statement above.
- [x] Each alert has an owner and a defined action (section 3).
- [x] No log file, database or personal data is in the Git repository or the container image (`logs/` and `*.db` are in `.gitignore` and `.dockerignore`; the submission zip contains no `.db` file; the sample CSV holds only simulated and test rows).

**Note on the live service.** The code in this folder logs every request, but the service already running on Render (6.4) was built before this change. To log on Render, upload the updated files and redeploy; its log would live on temporary storage, as described in the privacy statement.
