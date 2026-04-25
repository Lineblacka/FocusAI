import logging
import time
from typing import Iterable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from storage.rate_limit_store import RateLimitStore

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.time()
        response = await call_next(request)
        latency = round(time.time() - started, 4)
        logger.info('http_request method=%s path=%s status=%s latency=%s', request.method, request.url.path, response.status_code, latency)
        return response


def _normalize_trusted_proxies(trusted_proxies: Iterable[str] | None) -> set[str]:
    return {item.strip() for item in (trusted_proxies or []) if item and item.strip()}


def _is_trusted_proxy(client_host: str, trusted_proxies: set[str]) -> bool:
    return '*' in trusted_proxies or client_host in trusted_proxies


def client_key_from_request(request: Request, trusted_proxies: Iterable[str] | None = None) -> str:
    trusted_proxy_set = _normalize_trusted_proxies(trusted_proxies)
    client_host = request.client.host if request.client else 'unknown'

    if _is_trusted_proxy(client_host, trusted_proxy_set):
        forwarded_for = request.headers.get('x-forwarded-for', '')
        if forwarded_for:
            first_ip = forwarded_for.split(',')[0].strip()
            if first_ip:
                return first_ip

        real_ip = request.headers.get('x-real-ip', '').strip()
        if real_ip:
            return real_ip

    return client_host


class PersistentRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, store: RateLimitStore, limit_per_minute: int, trusted_proxies: Iterable[str] | None = None):
        super().__init__(app)
        self.store = store
        self.limit = limit_per_minute
        self.trusted_proxies = _normalize_trusted_proxies(trusted_proxies)

    async def dispatch(self, request: Request, call_next):
        client_key = client_key_from_request(request, self.trusted_proxies)
        if not self.store.check_and_record(client_key, self.limit):
            return JSONResponse(status_code=429, content={'detail': 'Rate limit exceeded'})
        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get('content-length')
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(status_code=413, content={'detail': 'Request body too large'})
            except ValueError:
                return JSONResponse(status_code=400, content={'detail': 'Invalid Content-Length header'})
        else:
            body = await request.body()
            if len(body) > self.max_bytes:
                return JSONResponse(status_code=413, content={'detail': 'Request body too large'})
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "font-src 'self' data:; "
            "connect-src 'self' http://localhost:5173 ws://localhost:5173 http://127.0.0.1:5173 ws://127.0.0.1:5173; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        return response
