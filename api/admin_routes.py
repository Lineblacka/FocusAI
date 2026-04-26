import hmac
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from api.middleware import client_key_from_request
from services.admin_auth import COOKIE_NAME, SESSION_TTL_HOURS, create_admin_session, verify_admin_session

router = APIRouter(prefix='/admin', tags=['admin'])
BASE_DIR = Path(__file__).resolve().parent.parent
ADMIN_LOGIN_HTML = BASE_DIR / 'app' / 'admin_pages' / 'login.html'
ADMIN_DASHBOARD_HTML = BASE_DIR / 'app' / 'admin_pages' / 'dashboard.html'

class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=240)


def require_admin(request: Request) -> Dict[str, Any]:
    settings = request.app.state.settings
    session = verify_admin_session(request.cookies.get(COOKIE_NAME), settings.admin_session_secret)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    return session


def _current_admin(request: Request) -> Dict[str, Any] | None:
    settings = request.app.state.settings
    return verify_admin_session(request.cookies.get(COOKIE_NAME), settings.admin_session_secret)


def _cookie_secure(request: Request) -> bool:
    # Secure cookies are required in real HTTPS production, but they are not stored
    # by browsers on http://127.0.0.1 / localhost during local development.
    forwarded_proto = request.headers.get('x-forwarded-proto', '').split(',')[0].strip().lower()
    host = request.url.hostname or ''
    is_local = host in {'127.0.0.1', 'localhost', '0.0.0.0'} or host.startswith('192.168.') or host.startswith('10.')
    return (request.url.scheme == 'https' or forwarded_proto == 'https') and not is_local


@router.get('', include_in_schema=False)
def admin_root(request: Request):
    return RedirectResponse('/admin/analytics' if _current_admin(request) else '/admin/login', status_code=302)


@router.get('/login', include_in_schema=False)
def admin_login_page(request: Request):
    if _current_admin(request):
        return RedirectResponse('/admin/analytics', status_code=302)
    return FileResponse(ADMIN_LOGIN_HTML)


@router.get('/analytics', include_in_schema=False)
def admin_analytics_page(request: Request):
    if not _current_admin(request):
        return RedirectResponse('/admin/login', status_code=302)
    return FileResponse(ADMIN_DASHBOARD_HTML)



@router.get('/assets/{asset_name}', include_in_schema=False)
def admin_asset(asset_name: str):
    allowed = {
        'login.js': BASE_DIR / 'app' / 'admin_pages' / 'login.js',
        'dashboard.js': BASE_DIR / 'app' / 'admin_pages' / 'dashboard.js',
    }
    path = allowed.get(asset_name)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail='Not found')
    return FileResponse(path, media_type='application/javascript')

@router.post('/login')
def admin_login(payload: AdminLoginRequest, request: Request, response: Response):
    settings = request.app.state.settings
    analytics_store = request.app.state.analytics_store
    client_ip = client_key_from_request(request, settings.trusted_proxies)

    locked, _locked_until = analytics_store.is_login_locked(client_ip)
    if locked:
        raise HTTPException(status_code=429, detail='Too many failed attempts. Try again later.')

    valid_username = hmac.compare_digest(payload.username, settings.admin_username)
    valid_password = hmac.compare_digest(payload.password, settings.admin_password)
    if not valid_username or not valid_password:
        locked_until = analytics_store.record_login_failure(client_ip)
        detail = 'Invalid username or password.' if not locked_until else 'Too many failed attempts. Temporary lockout enabled.'
        raise HTTPException(status_code=401, detail=detail)

    analytics_store.record_login_success(client_ip)
    token = create_admin_session(settings.admin_username, settings.admin_session_secret)
    response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, secure=_cookie_secure(request), samesite='lax', max_age=SESSION_TTL_HOURS * 60 * 60, path='/')
    return {'ok': True, 'username': settings.admin_username}


@router.post('/logout')
def admin_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path='/')
    return {'ok': True}


@router.get('/me')
def admin_me(session: Dict[str, Any] = Depends(require_admin)):
    return {'authenticated': True, 'username': session.get('sub')}


@router.get('/analytics/data')
def admin_analytics_data(request: Request, _: Dict[str, Any] = Depends(require_admin)):
    return request.app.state.analytics_store.summary()


@router.get('/analytics/export')
def admin_analytics_export(request: Request, _: Dict[str, Any] = Depends(require_admin)):
    return request.app.state.analytics_store.export_all()


@router.post('/analytics/clear')
def admin_analytics_clear(request: Request, _: Dict[str, Any] = Depends(require_admin)):
    request.app.state.analytics_store.clear_activity()
    return {'ok': True}
