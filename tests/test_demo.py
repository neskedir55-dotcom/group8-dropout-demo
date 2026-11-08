"""UI failure handling is mocked; test_live_api verifies the selected API."""
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from streamlit.testing.v1 import AppTest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('demo_client', HERE / 'streamlit_app.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def reply(**overrides):
    result = dict(probability=0.2, threshold=0.38, risk_label='low_risk',
                  predicted_outcome='Graduate', model_version='1.0.0',
                  probabilities={'Dropout': 0.2, 'Enrolled': 0.3, 'Graduate': 0.5})
    result.update(overrides)
    return Mock(status_code=200, json=Mock(return_value=result))


@pytest.mark.parametrize('response,message', [
    (Mock(status_code=422), 'Some inputs are invalid'),
    (Mock(status_code=500), 'could not complete'),
    (Mock(status_code=401), 'could not complete'),
    (Mock(status_code=200, json=Mock(side_effect=ValueError)), 'could not be read'),
    (reply(probability=float('nan')), 'could not be read'),
    (reply(probability=True), 'could not be read'),
    (reply(probabilities={}), 'could not be read'),
    (reply(predicted_outcome='Approved'), 'could not be read'),
    (reply(risk_label='high_risk'), 'could not be read'),
    (Mock(status_code=200, json=Mock(return_value=[])), 'could not be read'),
])
def test_bad_responses(response, message):
    with patch.object(client.requests, 'post', return_value=response):
        with pytest.raises(client.DemoError, match=message):
            client.request_prediction({})


@pytest.mark.parametrize('exc,message', [
    (requests.Timeout('private detail'), 'took too long'),
    (requests.ConnectionError('private detail'), 'Could not reach'),
])
def test_network_failures(exc, message):
    with patch.object(client.requests, 'post', side_effect=exc):
        with pytest.raises(client.DemoError, match=message):
            client.request_prediction({})


def test_ui_posts_all_fields_and_shows_estimate():
    app = AppTest.from_file(str(HERE / 'streamlit_app.py')).run()
    assert not app.exception
    assert len(app.number_input) + len(app.selectbox) - 1 == 28
    with patch('requests.post', return_value=reply()) as post:
        app.button[0].click().run()
    assert not app.exception
    payload = post.call_args.kwargs['json']
    assert set(payload) == {f['key'] for f in client.CONTRACT}
    assert post.call_args.kwargs['timeout'] == 60
    assert app.metric[0].value == '20.0%'
    assert any('final decision' in info.value for info in app.info)


def test_failed_submission_clears_previous_result():
    app = AppTest.from_file(str(HERE / 'streamlit_app.py')).run()
    with patch('requests.post', return_value=reply()):
        app.button[0].click().run()
    with patch('requests.post', side_effect=requests.ConnectionError('SECRET')):
        app.button[0].click().run()
    assert not app.exception
    assert not app.metric
    assert 'Could not reach' in app.error[0].value
    assert 'SECRET' not in app.error[0].value


def test_example_change_resets_result_and_fields():
    app = AppTest.from_file(str(HERE / 'streamlit_app.py')).run()
    with patch('requests.post', return_value=reply()):
        app.button[0].click().run()
    name = list(client.SCENARIOS)[-1]
    app.selectbox[0].select(name).run()
    assert not app.exception
    assert not app.metric
    for key, value in client.SCENARIOS[name].items():
        assert app.session_state[f'input_{name}_{key}'] == value


@pytest.mark.skipif(os.getenv('LIVE_API') != '1', reason='Set LIVE_API=1 to test the configured API')
def test_live_api():
    schema = requests.get(f'{client.API_URL}/openapi.json', timeout=60).json()
    inputs = schema['components']['schemas']['PredictionInput']
    assert set(inputs['required']) == {f['key'] for f in client.CONTRACT}
    for field in client.CONTRACT:
        prop = inputs['properties'][field['key']]
        if 'options' in field:
            assert prop['enum'] == field['options']
        else:
            assert prop['minimum'] == field['min']
            assert prop['maximum'] == field['max']
            assert prop['type'] == ('integer' if field['type'] == 'int' else 'number')
    results = {name: client.request_prediction(values) for name, values in client.SCENARIOS.items()}
    assert any(r['risk_label'] == 'low_risk' for r in results.values())
    assert any(r['risk_label'] == 'high_risk' for r in results.values())
    assert any(abs(r['probability'] - r['threshold']) <= 0.01 for r in results.values())
    invalid = dict(next(iter(client.SCENARIOS.values())))
    invalid.pop('Age at enrollment')
    with pytest.raises(client.DemoError, match='Some inputs are invalid'):
        client.request_prediction(invalid)
