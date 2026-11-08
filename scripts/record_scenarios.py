"""Record actual API results, including rejected input; run with the API up."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from streamlit_app import API_URL, SCENARIOS, request_prediction

folder = HERE / 'evidence'
folder.mkdir(exist_ok=True)
results = {name: {'inputs': inputs, 'result': request_prediction(inputs)}
           for name, inputs in SCENARIOS.items()}
(folder / 'scenario_results.json').write_text(json.dumps(results, indent=2) + '\n')
invalid = dict(next(iter(SCENARIOS.values())))
invalid.pop('Age at enrollment')
r = requests.post(f'{API_URL}/predict', json=invalid, timeout=60)
assert r.status_code == 422
(folder / 'invalid_input.json').write_text(json.dumps({
    'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
    'api_url': API_URL, 'request': invalid, 'status': r.status_code, 'response': r.json(),
}, indent=2) + '\n')
for name, record in results.items():
    result = record['result']
    print(f"{name}: {result['probability']:.2%}, {result['risk_label']}, {result['predicted_outcome']}")
print('Missing age: HTTP 422 (rejected as expected)')
