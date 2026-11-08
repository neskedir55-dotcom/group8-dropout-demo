"""Module 6.5: a small API client; no model or ML libraries are loaded here."""
import json
import math
import os
from pathlib import Path

import requests
import streamlit as st

def secret_api_url():
    try:
        return st.secrets.get("API_URL")
    except FileNotFoundError:
        return None


API_URL = (os.getenv("API_URL") or secret_api_url() or "https://group-8-student-dropout-risk-api.onrender.com").rstrip("/")

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "input_contract.json").read_text())
SCENARIOS = json.loads((HERE / "scenarios.json").read_text())
CLASSES = ("Dropout", "Enrolled", "Graduate")
LABELS = {
    "Nacionality": "Nationality (dataset code)",
    "Age at enrollment": "Age at enrollment (years)",
    "Unemployment rate": "Unemployment rate (%)",
    "Inflation rate": "Inflation rate (%)",
    "GDP": "GDP growth (%)",
    "Curricular units 1st sem (credited)": "Courses credited in semester 1 (count)",
    "Curricular units 1st sem (enrolled)": "Courses enrolled in semester 1 (count)",
    "Curricular units 1st sem (evaluations)": "Assessments in semester 1 (count)",
    "Curricular units 1st sem (approved)": "Courses passed in semester 1 (count)",
    "Curricular units 1st sem (grade)": "Average semester 1 grade (0–20 scale)",
    "Curricular units 1st sem (without evaluations)": "Courses without assessments (count)",
}
CHOICES = {
    "Daytime/evening attendance": {0: "Evening", 1: "Daytime"},
    "Gender": {0: "Female (dataset category)", 1: "Male (dataset category)"},
    "Marital status": {1: "Single", 2: "Married", 3: "Widowed", 4: "Divorced", 5: "De facto union", 6: "Legally separated"},
}


class DemoError(Exception):
    """A message safe to display to a user."""


def validate_result(result):
    """Reject unusable responses rather than displaying misleading estimates."""
    def probability(value):
        return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1

    try:
        probs = result["probabilities"]
        p, threshold = result["probability"], result["threshold"]
        valid = (
            probability(p) and probability(threshold)
            and all(probability(probs[name]) for name in CLASSES)
            and abs(sum(probs[name] for name in CLASSES) - 1) <= 0.001
            and abs(p - probs["Dropout"]) <= 0.0001
            and result["predicted_outcome"] in CLASSES
            and result["risk_label"] in ("high_risk", "low_risk")
            and (result["risk_label"] == "high_risk") == (result["predicted_outcome"] == "Dropout")
            and isinstance(result["model_version"], str) and bool(result["model_version"])
        )
        if not valid:
            raise ValueError
        # Allow API rounding at the boundary: decisions use unrounded probabilities.
        if abs(p - threshold) > 0.0001:
            if (p >= threshold) != (result["risk_label"] == "high_risk"):
                raise ValueError
    except (ValueError, KeyError, TypeError):
        raise DemoError("The service sent an answer that could not be read. Please try again later.") from None
    return result


def request_prediction(payload):
    try:
        response = requests.post(f"{API_URL}/predict", json=payload, timeout=60)
    except requests.Timeout:
        raise DemoError("The service took too long to respond. It may be waking up; wait a minute and try again.") from None
    except requests.RequestException:
        raise DemoError("Could not reach the service. Please try again when the service is available.") from None
    if response.status_code == 422:
        raise DemoError("Some inputs are invalid. Check the student details and allowed codes, then try again.")
    if response.status_code != 200:
        raise DemoError("The service could not complete the estimate. Please try again later.")
    try:
        result = response.json()
    except ValueError:
        raise DemoError("The service sent an answer that could not be read. Please try again later.") from None
    return validate_result(result)


def clear_result():
    st.session_state.pop("prediction", None)


def load_example():
    clear_result()


def widget(field, default):
    key = field["key"]
    widget_key = f"input_{st.session_state.example}_{key}"
    label = LABELS.get(key, key)
    help_text = field["description"]
    if "options" in field:
        options = field["options"]
        known = CHOICES.get(key, {0: "No", 1: "Yes"} if options == [0, 1] else {})
        return st.selectbox(
            label, options, index=options.index(default), key=widget_key,
            format_func=lambda v: f"{known[v]} · {v}" if v in known else f"Dataset code {v}",
            help=f"{help_text} Allowed codes: {', '.join(map(str, options))}. "
                 "For coded categories use the project's dataset encoding; do not guess a code.",
        )
    cast = int if field["type"] == "int" else float
    low, high = cast(field["min"]), cast(field["max"])
    return st.number_input(
        label, min_value=low, max_value=high, value=cast(default),
        step=1 if cast is int else 0.001,
        format="%d" if cast is int else "%.3f", key=widget_key,
        help=f"{help_text} Accepted range: {low} to {high}.",
    )


def main():
    st.set_page_config(page_title="Student Support · Group 8", page_icon="🎓", layout="centered")
    st.caption("GROUP 8 · STUDENT SUPPORT · MODULE 6.5")
    st.title("Student early-warning demo")
    st.write("Explore an estimate of dropout risk using information available at the end of semester 1.")
    st.info("Educational demonstration. An adviser must review the student's circumstances before any action.")
    with st.expander("Who this is for, and what the model can miss"):
        st.write("For student advisers and project reviewers exploring early support needs. "
                 "The model learned associations from historical student records; it cannot determine why a student may leave.")
        st.write("Known limitations: lower dropout recall for students aged 19 or under, female students, "
                 "and displaced students. It often misses students with strong first-semester results who later leave. "
                 "The Enrolled class is the weakest class.")
        st.write("Use synthetic examples here. Do not enter names or student IDs. "
                 "A low estimate does not mean a student needs no support. Never use this estimate alone for admissions, discipline, or funding.")
    st.selectbox("Start with an example", list(SCENARIOS), key="example", on_change=load_example)
    st.caption("Examples are demonstration inputs. Review every field before requesting an estimate. "
               "Some categories retain dataset codes because a verified code-to-name dictionary is unavailable.")
    defaults = SCENARIOS[st.session_state.example]
    payload = {}
    with st.form("student_details"):
        st.subheader("Student details")
        groups = [
            ("Semester 1 learning", lambda k: k.startswith("Curricular")),
            ("Enrollment and background", lambda k: not k.startswith("Curricular") and k not in ("Unemployment rate", "Inflation rate", "GDP")),
            ("Economic context", lambda k: k in ("Unemployment rate", "Inflation rate", "GDP")),
        ]
        for title, matches in groups:
            with st.expander(title, expanded=title == "Semester 1 learning"):
                for field in CONTRACT:
                    if matches(field["key"]):
                        payload[field["key"]] = widget(field, defaults[field["key"]])
        submitted = st.form_submit_button("Estimate support needs", type="primary", use_container_width=True)
    if submitted:
        clear_result()
        try:
            with st.spinner("Contacting the service. A sleeping service may take up to a minute."):
                result = request_prediction(payload)
            st.session_state.prediction = {"inputs": payload, "result": result}
        except DemoError as exc:
            st.error(str(exc))
    if "prediction" not in st.session_state:
        return
    saved = st.session_state.prediction
    result = saved["result"]
    p, threshold = result["probability"], result["threshold"]
    flagged = result["risk_label"] == "high_risk"
    st.subheader("Model estimate")
    st.caption("This result belongs to the last submitted details. Submit again after editing the form.")
    st.metric("Estimated chance of dropout", f"{p:.1%}")
    st.write(f"The model estimates about a **{p:.1%} chance of dropout** for this example. "
             f"The model's predicted outcome is **{result['predicted_outcome']}**.")
    message = ("Early-warning flag: an adviser should review possible support needs." if flagged else
               "Below the warning threshold: this does not rule out a need for support.")
    if flagged:
        st.warning(message)
    else:
        st.success(message)
    st.caption(f"The service flags dropout at {threshold:.1%}. Below that threshold it chooses "
               "the more likely of Enrolled and Graduate. This rule may differ from choosing the largest probability.")
    if abs(p - threshold) <= 0.03:
        st.warning("Close to the warning threshold. Small changes in the inputs may change the warning; human review is especially important.")
    for name in CLASSES:
        st.progress(result["probabilities"][name], text=f"{name}: {result['probabilities'][name]:.1%}")
    st.info("This is a model estimate, not a verified fact or a final decision. A qualified adviser makes the final judgment.")
    with st.expander("Submitted details and model version"):
        st.caption(f"Model version: {result['model_version']}")
        st.json(saved["inputs"])
    st.download_button("Download this estimate (JSON)", json.dumps(saved, indent=2),
                       file_name="student_support_estimate.json", mime="application/json")


if __name__ == "__main__":
    main()
