import os
from datetime import datetime

os.environ.setdefault('OPENROUTER_API_KEY', 'test-key')

from config.settings import get_settings
from services.ai_service import AIService
from services.intent_service import IntentService
from services.quality_service import QualityService


def test_build_messages_uses_normal_mode_prompt():
    get_settings.cache_clear()
    settings = get_settings()
    service = AIService(settings, QualityService(), IntentService())

    intent, messages = service.build_messages(
        {'profile': {'goals': ['дисциплина'], 'bad_patterns': [], 'commitments': []}, 'messages': []},
        'Кой си ти',
        'normal',
    )

    assert intent == 'identity_question'
    assert 'sharp but supportive productivity coach' in messages[0]['content']
    assert 'Режим: normal' in messages[1]['content']


def test_build_messages_uses_brutal_mode_prompt():
    get_settings.cache_clear()
    settings = get_settings()
    service = AIService(settings, QualityService(), IntentService())

    intent, messages = service.build_messages(
        {'profile': {'goals': ['дисциплина'], 'bad_patterns': [], 'commitments': []}, 'messages': []},
        'Кой си ти',
        'brutal',
    )

    assert intent == 'identity_question'
    assert 'BRUTAL MODE' in messages[0]['content']
    assert 'Режим: brutal' in messages[1]['content']


def test_quick_reply_changes_with_mode():
    get_settings.cache_clear()
    settings = get_settings()
    service = AIService(settings, QualityService(), IntentService())

    normal = service.quick_reply('Кой си ти?', 'normal')
    brutal = service.quick_reply('Кой си ти?', 'brutal')

    assert normal is not None
    assert brutal is not None
    assert 'Аз съм FocusAI' in normal['content']
    assert 'Не съм тук да те галя' in brutal['content']
    assert 'OpenAI' not in normal['content']
    assert 'GPT-4' not in brutal['content']


def test_quick_reply_returns_current_year():
    get_settings.cache_clear()
    settings = get_settings()
    service = AIService(settings, QualityService(), IntentService())

    result = service.quick_reply('Коя година сме?', 'normal')

    assert result is not None
    assert result['intent'] == 'time_question'
    assert str(datetime.now().year) in result['content']


def test_build_messages_filters_tainted_assistant_history():
    get_settings.cache_clear()
    settings = get_settings()
    service = AIService(settings, QualityService(), IntentService())

    intent, messages = service.build_messages(
        {
            'profile': {'goals': [], 'bad_patterns': [], 'commitments': []},
            'messages': [
                {'role': 'user', 'content': 'Ей човек просто нямам мотивацията'},
                {
                    'role': 'assistant',
                    'content': 'We responded. Като AI модел от OpenAI, работя върху архитектурата GPT-4.',
                },
            ],
        },
        'Помогни ми да започна',
        'brutal',
    )

    assert intent in {'goal_planning', 'general_question'}
    history_contents = [message['content'] for message in messages if message['role'] != 'system']
    assert not any('We responded.' in content for content in history_contents)
    assert not any('OpenAI' in content for content in history_contents)
    assert not any('GPT-4' in content for content in history_contents)


def test_extract_chat_content_reads_text_blocks():
    get_settings.cache_clear()
    settings = get_settings()
    service = AIService(settings, QualityService(), IntentService())

    content = service._extract_chat_content(
        {
            'choices': [
                {
                    'message': {
                        'content': [
                            {'type': 'text', 'text': 'Focus'},
                            {'type': 'text', 'text': 'AI'},
                        ]
                    }
                }
            ]
        }
    )

    assert content == 'FocusAI'


def test_iter_stream_deltas_reads_openrouter_sse():
    get_settings.cache_clear()
    settings = get_settings()
    service = AIService(settings, QualityService(), IntentService())

    class StubResponse:
        def __init__(self):
            self.closed = False

        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"Hel"}}]}'
            yield 'data: {"choices":[{"delta":{"content":[{"type":"text","text":"lo"}]}}]}'
            yield 'data: [DONE]'

        def close(self):
            self.closed = True

    response = StubResponse()
    deltas = list(service._iter_stream_deltas(response))

    assert deltas == ['Hel', 'lo']
    assert response.closed is True
