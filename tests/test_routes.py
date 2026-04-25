import os
import asyncio

os.environ.setdefault('OPENROUTER_API_KEY', 'test-key')

from fastapi.testclient import TestClient
from starlette.requests import Request

from api.middleware import RequestSizeLimitMiddleware, client_key_from_request
from app.main import create_app
from config.settings import get_settings


class StubAIService:
    def __init__(self):
        self.last_messages = None
        self.last_mode = None

    def quick_reply(self, user_input, mode='normal'):
        self.last_mode = mode
        return None

    def build_messages(self, memory, user_input, mode='normal', search_context=None):
        self.last_messages = memory.get('messages', [])
        self.last_mode = mode
        messages = [{'role': 'system', 'content': f'mode:{mode}'}, {'role': 'user', 'content': user_input}]
        if search_context:
            messages.insert(1, {'role': 'system', 'content': search_context})
        return 'general_question', messages

    def ask(self, messages):
        return {'content': 'Направи първия ход днес.', 'model': 'stub-model', 'latency_seconds': 0.12, 'error': None}

    def stream(self, messages):
        yield {'type': 'done', 'content': 'Направи първия ход днес.', 'model': 'stub-model', 'latency_seconds': 0.12, 'error': None}


class StubWebSearchService:
    def build_context(self, query, preference='auto'):
        if preference == 'on':
            return 'Свеж уеб контекст за текущата заявка:\n1. Пример', {'used': True, 'query': query, 'results': [{'title': 'Пример'}]}
        return None, {'used': False, 'query': query, 'results': []}


def test_chat_uses_isolated_session_memory(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    stub = StubAIService()
    app.state.ai_service = stub
    app.state.web_search_service = StubWebSearchService()
    client = TestClient(app)

    first = client.post('/chat', json={'message': 'Първи чат', 'session_id': 'session-a', 'mode': 'normal'}, headers={'host': 'localhost'})
    second = client.post('/chat', json={'message': 'Втори чат', 'session_id': 'session-b', 'mode': 'brutal'}, headers={'host': 'localhost'})

    assert first.status_code == 200
    assert second.status_code == 200

    session_a = app.state.memory_store.load_session('session-a')
    session_b = app.state.memory_store.load_session('session-b')

    assert any(item['content'] == 'Първи чат' for item in session_a['messages'])
    assert not any(item['content'] == 'Първи чат' for item in session_b['messages'])
    assert stub.last_mode == 'brutal'


def test_request_size_limit_rejects_large_body(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)
    huge = 'а' * 70000

    response = client.post('/chat', json={'message': huge, 'session_id': 'default', 'mode': 'normal'}, headers={'host': 'localhost'})

    assert response.status_code in {413, 422}


def test_chat_rejects_invalid_mode(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)

    response = client.post('/chat', json={'message': 'Здравей', 'session_id': 'default', 'mode': 'wild'}, headers={'host': 'localhost'})

    assert response.status_code == 422


def test_chat_accepts_web_search_flag(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    app.state.ai_service = StubAIService()
    app.state.web_search_service = StubWebSearchService()
    client = TestClient(app)

    response = client.post(
        '/chat',
        json={'message': 'Провери последните новини за Bitcoin', 'session_id': 'default', 'mode': 'normal', 'web_search': 'on'},
        headers={'host': 'localhost'},
    )

    assert response.status_code == 200
    assert response.json()['reply'] == 'Направи първия ход днес.'
    assert response.json()['sources'] == [{'title': 'Пример'}]


def test_rate_limit_uses_forwarded_ip_and_separates_clients(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('RATE_LIMIT_PER_MINUTE', '1')
    monkeypatch.setenv('TRUSTED_PROXIES', 'testclient')
    get_settings.cache_clear()
    app = create_app()
    app.state.ai_service = StubAIService()
    app.state.web_search_service = StubWebSearchService()
    client = TestClient(app)

    first = client.post(
        '/chat',
        json={'message': 'Първо', 'session_id': 'default', 'mode': 'normal'},
        headers={'host': 'localhost', 'x-forwarded-for': '203.0.113.10'},
    )
    second = client.post(
        '/chat',
        json={'message': 'Второ', 'session_id': 'default', 'mode': 'normal'},
        headers={'host': 'localhost', 'x-forwarded-for': '203.0.113.10'},
    )
    third = client.post(
        '/chat',
        json={'message': 'Трето', 'session_id': 'default', 'mode': 'normal'},
        headers={'host': 'localhost', 'x-forwarded-for': '203.0.113.11'},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert third.status_code == 200


def test_client_key_ignores_forwarded_headers_from_untrusted_clients():
    scope = {
        'type': 'http',
        'method': 'POST',
        'path': '/chat',
        'headers': [
            (b'x-forwarded-for', b'203.0.113.10'),
            (b'x-real-ip', b'203.0.113.20'),
        ],
        'client': ('198.51.100.7', 12345),
    }

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    request = Request(scope, receive)
    assert client_key_from_request(request, trusted_proxies=[]) == '198.51.100.7'


def test_request_size_limit_rejects_large_body_without_content_length():
    middleware = RequestSizeLimitMiddleware(app=lambda scope, receive, send: None, max_bytes=8)
    scope = {
        'type': 'http',
        'method': 'POST',
        'path': '/chat',
        'headers': [],
        'client': ('127.0.0.1', 12345),
    }

    async def receive():
        return {'type': 'http.request', 'body': b'0123456789', 'more_body': False}

    request = Request(scope, receive)

    async def call_next(_request):
        raise AssertionError('call_next should not be reached for oversized bodies')

    response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.status_code == 413
