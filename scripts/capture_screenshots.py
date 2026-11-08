"""Capture real UI states. Requires Playwright + Chromium and two demo servers.

Normal server: localhost:8501 (local Docker API).
Failure server: localhost:8502 (API_URL=http://127.0.0.1:1).
Optional CHROMIUM_PATH selects an existing browser executable.
"""
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

EVIDENCE = Path(__file__).resolve().parents[1] / 'evidence'
EVIDENCE.mkdir(exist_ok=True)
with sync_playwright() as p:
    options = {'headless': True, 'args': ['--no-sandbox']}
    if os.getenv('CHROMIUM_PATH'):
        options['executable_path'] = os.environ['CHROMIUM_PATH']
    browser = p.chromium.launch(**options)
    page = browser.new_page(viewport={'width': 1280, 'height': 2400})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8501')
    button = page.get_by_role('button', name='Estimate support needs')
    button.wait_for()
    for name, filename, estimate in [
        ('Low-risk example', 'low_risk.png', '0.3%'),
        ('High-risk example', 'high_risk.png', '78.1%'),
        ('Borderline example', 'borderline.png', '38.3%'),
    ]:
        page.goto('http://127.0.0.1:8501')
        button.wait_for()
        if name != 'Low-risk example':
            page.get_by_role('combobox').first.click()
            page.get_by_role('option', name=name, exact=True).click()
        passed = {'Low-risk example': '6', 'High-risk example': '0', 'Borderline example': '2'}[name]
        expect(page.get_by_role('spinbutton', name='Courses passed in semester 1 (count)', exact=True)).to_have_value(passed)
        button.click()
        page.get_by_test_id('stMetricValue').filter(has_text=estimate).wait_for()
        assert page.get_by_text('This is a model estimate, not a verified fact or a final decision.', exact=False).count()
        assert not page.get_by_test_id('stException').count()
        assert not page.get_by_test_id('stDocString').count()
        page.get_by_test_id('stMain').evaluate('(el) => el.scrollTop = 0')
        page.screenshot(path=str(EVIDENCE / filename), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.set_viewport_size({'width': 390, 'height': 3200})
    page.get_by_test_id('stMain').evaluate('(el) => el.scrollTop = 0')
    page.screenshot(path=str(EVIDENCE / 'mobile_borderline.png'), full_page=True)
    page.goto('http://127.0.0.1:8502')
    page.get_by_role('button', name='Estimate support needs').click()
    page.get_by_text('Could not reach the service.', exact=False).wait_for()
    assert not page.get_by_test_id('stException').count()
    assert not page.get_by_test_id('stMetricValue').count()
    page.get_by_test_id('stMain').evaluate('(el) => el.scrollTop = 0')
    page.screenshot(path=str(EVIDENCE / 'unavailable_service.png'), full_page=True)
    assert not errors, errors
    browser.close()
print('Captured three live predictions, phone-width layout and a real connection failure.')
