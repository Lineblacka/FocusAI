import os

os.environ.setdefault('OPENROUTER_API_KEY', 'test-key')

from fastapi.testclient import TestClient

from app.main import create_app
from config.settings import get_settings


def test_health(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get('/health', headers={'host': 'localhost'})
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert data['app'] == 'FocusAI'


def test_security_headers_present(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get('/health', headers={'host': 'localhost'})
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert 'frame-ancestors' in response.headers['content-security-policy']
