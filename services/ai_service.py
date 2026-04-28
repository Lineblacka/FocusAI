import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Generator, List

import cloudscraper

from app.prompts import BRUTAL_MODE_PROMPT, NORMAL_MODE_PROMPT
from config.settings import Settings
from services.intent_service import IntentService
from services.quality_service import QualityService

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, settings: Settings, quality_service: QualityService, intent_service: IntentService):
        self.settings = settings
        self.quality = quality_service
        self.intent = intent_service
        self.user_agent = 'FocusAI/1.0 (+https://github.com/Lineblacka)'
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        self.scraper.headers.update(
            {
                'Authorization': f'Bearer {settings.openrouter_api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': self.user_agent,
            }
        )

    def system_prompt_for_mode(self, mode: str) -> str:
        return BRUTAL_MODE_PROMPT if mode == 'brutal' else NORMAL_MODE_PROMPT

    def build_profile_context(self, memory: Dict[str, Any]) -> str:
        profile = memory.get('profile', {})
        return (
            'Контекст за потребителя:\n'
            f'- Цели: {profile.get("goals", []) or "няма записани"}\n'
            f'- Повтарящи се проблеми: {profile.get("bad_patterns", []) or "няма записани"}\n'
            f'- Ангажименти: {profile.get("commitments", []) or "няма записани"}\n'
        )

    def behavior_instruction(self, intent: str, mode: str) -> str:
        normal_instructions = {
            'identity_question': 'Отговори естествено кой си и как помагаш, без да споменаваш доставчик, архитектура или вътрешно име на модел.',
            'time_question': 'Отговори с точната текуща локална дата, час или година, без догадки.',
            'small_talk': 'Отговори кратко и човешки.',
            'excuse': 'Разпознай оправданието и върни човека към изпълнима стъпка, свързана с неговите думи, не с измислен бизнес контекст.',
            'failure_report': 'Посочи какво се е объркало и дай ясен рестарт.',
            'goal_planning': 'Дай ясен план, минимална версия и критерий за успех.',
            'idea_review': 'Изясни идеята и дай конкретни следващи ходове.',
            'progress_report': 'Признай напредъка и посочи следващото ниво.',
            'emotional_support': 'Бъди спокоен, директен и безопасен.',
            'general_question': 'Отговори кратко, ясно и практично.',
        }

        brutal_instructions = {
            'identity_question': 'Отговори кратко и силно кой си и каква ти е ролята, без да споменаваш доставчик, архитектура или вътрешно име на модел.',
            'time_question': 'Отговори с точната текуща локална дата, час или година. Без театър.',
            'small_talk': 'Не се разливай. Върни разговора към действие веднага.',
            'excuse': 'Назови оправданието директно. Разбий го. Изисквай конкретен ангажимент, свързан с реалния проблем на човека.',
            'failure_report': 'Не утешавай. Покажи провала ясно и поискай точен следващ ход.',
            'goal_planning': 'Изисквай яснота, срок и ангажимент. Без общи приказки.',
            'idea_review': 'Режи мъглата. Ако идеята е слаба или неясна, кажи го директно.',
            'progress_report': 'Признай свършеното, после веднага натисни за следващото.',
            'emotional_support': 'Бъди твърд, но не опасен. Върни към контролируема стъпка.',
            'general_question': 'Бъди кратък, остър и изисквай конкретика.',
        }

        source = brutal_instructions if mode == 'brutal' else normal_instructions
        return source.get(intent, source['general_question'])

    def quick_reply(self, user_input: str, mode: str = 'normal') -> Dict[str, Any] | None:
        intent = self.intent.classify(user_input)
        now = datetime.now()
        lower_input = user_input.lower()

        if intent == 'time_question':
            if 'час' in lower_input:
                content = f'Сега е {now.strftime("%H:%M")}.'
            elif 'дата' in lower_input:
                content = f'Днес е {now.strftime("%d.%m.%Y")}.'
            else:
                content = f'Сега сме {now.year} г.'
            return {
                'intent': intent,
                'content': content,
                'model': None,
                'latency_seconds': 0.0,
                'error': None,
                'quality': self.quality.check(content),
            }

        canned = {
            'normal': {
                'identity_question': 'Аз съм FocusAI. Помагам ти да подредиш мислите си, да спреш оправданията и да стигаш до действие.',
                'small_talk': 'Тук съм. Какво искаш да задвижим днес?',
            },
            'brutal': {
                'identity_question': 'Аз съм FocusAI. Не съм тук да те галя, а да те вкарам в яснота, дисциплина и действие.',
                'small_talk': 'Стига общи приказки. Каква е задачата?',
            },
        }
        content = canned[mode].get(intent)
        if not content:
            return None
        return {
            'intent': intent,
            'content': content,
            'model': None,
            'latency_seconds': 0.0,
            'error': None,
            'quality': self.quality.check(content),
        }

    def build_messages(
        self,
        memory: Dict[str, Any],
        user_input: str,
        mode: str = 'normal',
        search_context: str | None = None,
    ) -> tuple[str, List[Dict[str, str]]]:
        intent = self.intent.classify(user_input)
        recent = memory.get('messages', [])[-self.settings.max_history_messages:]
        history = [
            {'role': msg['role'], 'content': self.quality.clean_output(msg['content'])}
            for msg in recent
            if msg.get('role') in {'user', 'assistant'}
            and msg.get('content')
            and self.quality.is_history_message_usable(msg.get('role', ''), msg.get('content', ''))
        ]
        context = (
            f'{self.build_profile_context(memory)}\n'
            f'Режим: {mode}\n'
            f'Текуща насока: {self.behavior_instruction(intent, mode)}'
        )
        messages: List[Dict[str, str]] = [
            {'role': 'system', 'content': self.system_prompt_for_mode(mode)},
            {'role': 'system', 'content': context},
        ]
        if search_context:
            messages.append({'role': 'system', 'content': search_context})
        messages.extend(history)
        messages.append({'role': 'user', 'content': user_input})
        return intent, messages

    def ask(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        last_error = None
        for model in self.settings.openrouter_models:
            for attempt in range(self.settings.empty_reply_retries + 1):
                started = time.time()
                try:
                    logger.info('model_attempt model=%s attempt=%s stream=false', model, attempt + 1)
                    response = self._create_chat_completion(model, messages, stream=False)
                    latency = round(time.time() - started, 2)
                    content = self.quality.clean_output(self._extract_chat_content(response.json()))
                    if self.quality.is_empty_or_weak(content):
                        logger.warning('empty_or_weak_response model=%s attempt=%s latency=%s', model, attempt + 1, latency)
                        last_error = 'empty_or_weak_response'
                        continue
                    logger.info('model_success model=%s latency=%s stream=false', model, latency)
                    return {'content': content, 'model': model, 'latency_seconds': latency, 'error': None}
                except Exception as exc:
                    if self._is_rate_limit_error(exc):
                        logger.warning('model_rate_limited model=%s error=%s', model, exc)
                    else:
                        logger.warning('model_api_error model=%s error=%s', model, exc)
                    last_error = str(exc)
                    break
        return {
            'content': 'Не получих стабилен отговор. Повтори задачата по-конкретно.',
            'model': None,
            'latency_seconds': None,
            'error': last_error,
        }

    def stream(self, messages: List[Dict[str, str]]) -> Generator[Dict[str, Any], None, None]:
        last_error = None

        for model in self.settings.openrouter_models:
            for attempt in range(self.settings.empty_reply_retries + 1):
                started = time.time()
                content_parts: List[str] = []

                try:
                    logger.info('model_attempt model=%s attempt=%s stream=true', model, attempt + 1)
                    yielded_any = False
                    response = self._create_chat_completion(model, messages, stream=True)
                    for delta in self._iter_stream_deltas(response):
                        if not delta:
                            continue
                        yielded_any = True
                        content_parts.append(delta)
                        yield {'type': 'delta', 'delta': delta, 'model': model}

                    latency = round(time.time() - started, 2)
                    content = self.quality.clean_output(''.join(content_parts))

                    if self.quality.is_empty_or_weak(content):
                        logger.warning(
                            'empty_or_weak_stream model=%s attempt=%s latency=%s yielded=%s',
                            model,
                            attempt + 1,
                            latency,
                            yielded_any,
                        )
                        last_error = 'empty_or_weak_response'
                        if yielded_any:
                            yield {'type': 'error', 'error': 'empty_or_weak_response_after_stream', 'model': model}
                            return
                        continue

                    logger.info('model_success model=%s latency=%s stream=true', model, latency)
                    yield {
                        'type': 'done',
                        'content': content,
                        'model': model,
                        'latency_seconds': latency,
                        'error': None,
                    }
                    return

                except Exception as exc:
                    if self._is_rate_limit_error(exc):
                        logger.warning('model_rate_limited model=%s stream=true error=%s', model, exc)
                    else:
                        logger.warning('model_api_error model=%s stream=true error=%s', model, exc)
                    last_error = str(exc)
                    break

        yield {
            'type': 'error',
            'content': 'Не получих стабилен отговор. Повтори задачата по-конкретно.',
            'model': None,
            'latency_seconds': None,
            'error': last_error,
        }

    def _chat_completions_url(self) -> str:
        return f'{self.settings.openrouter_base_url.rstrip("/")}/chat/completions'

    def _create_chat_completion(self, model: str, messages: List[Dict[str, str]], stream: bool):
        response = self.scraper.post(
            self._chat_completions_url(),
            json={
                'model': model,
                'messages': messages,
                'temperature': self.settings.model_temperature,
                'stream': stream,
            },
            timeout=self.settings.request_timeout_seconds,
            stream=stream,
        )
        response.raise_for_status()
        return response

    def _extract_chat_content(self, payload: Dict[str, Any]) -> str:
        choices = payload.get('choices') or []
        if not choices:
            return ''
        message = choices[0].get('message') or {}
        return self._coerce_content_to_text(message.get('content'))

    def _iter_stream_deltas(self, response) -> Generator[str, None, None]:
        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue

                line = raw_line.strip()
                if not line.startswith('data:'):
                    continue

                data = line[5:].strip()
                if data == '[DONE]':
                    return

                payload = json.loads(data)
                choices = payload.get('choices') or []
                if not choices:
                    continue

                delta = choices[0].get('delta') or {}
                text = self._coerce_content_to_text(delta.get('content'))
                if text:
                    yield text
        finally:
            response.close()

    def _coerce_content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                if item.get('type') == 'text' and item.get('text'):
                    parts.append(str(item['text']))
            return ''.join(parts)
        return ''

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        response = getattr(exc, 'response', None)
        return bool(response is not None and getattr(response, 'status_code', None) == 429)
