import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse, CommandRequest, CommandResponse, HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def track_chat_result(request: Request, session_id: str, model: str | None, latency_seconds: float | None, ok: bool = True, error: str | None = None) -> None:
    analytics_store = getattr(request.app.state, 'analytics_store', None)
    if analytics_store is None:
        return
    analytics_store.track_message(session_id=session_id, model=model, latency_seconds=latency_seconds, ok=ok)
    if not ok or error:
        analytics_store.track_error('chat', error or 'AI response failed', 502 if error else None)


def sse_event(event: str, payload: dict) -> str:
    return f'event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'


@router.get('/health', response_model=HealthResponse)
def health(request: Request):
    settings = request.app.state.settings
    return HealthResponse(status='ok', app=settings.app_name, env=settings.app_env, models=['FocusAI'])


@router.post('/chat', response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request):
    memory_store = request.app.state.memory_store
    ai_service = request.app.state.ai_service
    quality_service = request.app.state.quality_service
    web_search_service = request.app.state.web_search_service

    logger.info('Mode: %s web_search=%s', payload.mode, payload.web_search)

    search_context, search_meta = web_search_service.build_context(payload.message, payload.web_search)

    shortcut = None if payload.web_search == 'on' else ai_service.quick_reply(payload.message, payload.mode)
    if shortcut and not search_context:
        memory_store.append_turn(payload.message, shortcut['content'], shortcut['model'], shortcut['latency_seconds'], payload.session_id)
        track_chat_result(request, payload.session_id, shortcut['model'], shortcut['latency_seconds'])
        return ChatResponse(
            reply=shortcut['content'],
            model=None,
            latency_seconds=None,
            intent=shortcut['intent'],
            quality=shortcut['quality'],
            sources=[],
        )

    memory = memory_store.load_session(payload.session_id)
    intent, messages = ai_service.build_messages(memory, payload.message, payload.mode, search_context=search_context)
    result = ai_service.ask(messages)
    reply = quality_service.clean_output(result['content'])
    quality = quality_service.check(reply)
    memory_store.append_turn(payload.message, reply, result.get('model'), result.get('latency_seconds'), payload.session_id)
    track_chat_result(request, payload.session_id, result.get('model'), result.get('latency_seconds'), ok=not bool(result.get('error')), error=result.get('error'))

    if result.get('error') and not result.get('model'):
        raise HTTPException(status_code=502, detail={'message': reply, 'error': result.get('error')})

    return ChatResponse(
        reply=reply,
        model=None,
        latency_seconds=None,
        intent=intent,
        quality=quality,
        sources=search_meta.get('results', []),
    )


@router.post('/chat/stream')
def chat_stream(payload: ChatRequest, request: Request):
    memory_store = request.app.state.memory_store
    ai_service = request.app.state.ai_service
    quality_service = request.app.state.quality_service
    web_search_service = request.app.state.web_search_service

    logger.info('Mode: %s web_search=%s', payload.mode, payload.web_search)

    search_context, search_meta = web_search_service.build_context(payload.message, payload.web_search)

    shortcut = None if payload.web_search == 'on' else ai_service.quick_reply(payload.message, payload.mode)
    if shortcut and not search_context:
        def shortcut_generator():
            memory_store.append_turn(payload.message, shortcut['content'], shortcut['model'], shortcut['latency_seconds'], payload.session_id)
            track_chat_result(request, payload.session_id, shortcut['model'], shortcut['latency_seconds'])
            yield sse_event('start', {'intent': shortcut['intent'], 'mode': payload.mode, 'web_search_used': False})
            yield sse_event('done', {
                'reply': shortcut['content'],
                'model': None,
                'latency_seconds': None,
                'intent': shortcut['intent'],
                'quality': shortcut['quality'],
                'mode': payload.mode,
                'web_search_used': False,
                'sources': [],
            })

        return StreamingResponse(shortcut_generator(), media_type='text/event-stream')

    memory = memory_store.load_session(payload.session_id)
    intent, messages = ai_service.build_messages(memory, payload.message, payload.mode, search_context=search_context)

    def event_generator():
        yield sse_event('start', {'intent': intent, 'mode': payload.mode, 'web_search_used': bool(search_meta.get('used'))})

        for item in ai_service.stream(messages):
            item_type = item.get('type')

            if item_type == 'delta':
                yield sse_event('delta', {'delta': item.get('delta', '')})
                continue

            if item_type == 'done':
                final_content = quality_service.clean_output(item.get('content', ''))
                final_model = item.get('model')
                final_latency = item.get('latency_seconds')
                quality = quality_service.check(final_content)
                memory_store.append_turn(payload.message, final_content, final_model, final_latency, payload.session_id)
                track_chat_result(request, payload.session_id, final_model, final_latency)
                yield sse_event('done', {
                    'reply': final_content,
                    'model': None,
                    'latency_seconds': None,
                    'intent': intent,
                    'quality': quality,
                    'mode': payload.mode,
                    'web_search_used': bool(search_meta.get('used')),
                    'sources': search_meta.get('results', []),
                })
                return

            if item_type == 'error':
                final_content = quality_service.clean_output(item.get('content', 'Не получих стабилен отговор.'))
                final_model = item.get('model')
                final_latency = item.get('latency_seconds')
                final_error = item.get('error')
                memory_store.append_turn(payload.message, final_content, final_model, final_latency, payload.session_id)
                track_chat_result(request, payload.session_id, final_model, final_latency, ok=False, error=final_error)
                yield sse_event('error', {
                    'reply': final_content,
                    'model': None,
                    'latency_seconds': None,
                    'intent': intent,
                    'error': final_error,
                    'mode': payload.mode,
                    'web_search_used': bool(search_meta.get('used')),
                    'sources': search_meta.get('results', []),
                })
                return

    return StreamingResponse(event_generator(), media_type='text/event-stream')


@router.post('/command', response_model=CommandResponse)
def command(payload: CommandRequest, request: Request):
    result = request.app.state.command_service.handle(payload.command)
    return CommandResponse(**result)
