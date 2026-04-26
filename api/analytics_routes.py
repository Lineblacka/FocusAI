from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.middleware import client_key_from_request

router = APIRouter(prefix='/analytics', tags=['analytics'])


class AnalyticsEventRequest(BaseModel):
    event: str = Field(min_length=1, max_length=80)
    session_id: str = Field(default='', max_length=180)
    device: Dict[str, Any] = Field(default_factory=dict)


@router.post('/event')
def public_analytics_event(payload: AnalyticsEventRequest, request: Request):
    allowed = {'visit', 'chat_session', 'conversation_created', 'conversation_deleted'}
    if payload.event not in allowed:
        raise HTTPException(status_code=400, detail='Unsupported analytics event')

    analytics_store = getattr(request.app.state, 'analytics_store', None)
    if analytics_store is None:
        return {'ok': True}

    settings = getattr(request.app.state, 'settings', None)
    trusted = getattr(settings, 'trusted_proxies', []) if settings else []
    country_code = (
        request.headers.get('cf-ipcountry')
        or request.headers.get('x-vercel-ip-country')
        or request.headers.get('x-country-code')
        or ''
    ).upper()
    request_meta = {
        'ip': client_key_from_request(request, trusted),
        'country_code': country_code,
        'country_source': 'proxy_header' if country_code else '',
    }
    analytics_store.track_event(payload.event, session_id=payload.session_id, device=payload.device, request_meta=request_meta)
    return {'ok': True}
