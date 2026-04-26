import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

COOKIE_NAME = 'focusai_admin_session'
SESSION_TTL_HOURS = 8


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _unb64(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()


def create_admin_session(username: str, secret: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    payload = {
        'sub': username,
        'nonce': secrets.token_urlsafe(16),
        'exp': int(expires_at.timestamp()),
    }
    encoded = _b64(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    signature = _sign(encoded, secret)
    return f'{encoded}.{signature}'


def verify_admin_session(token: Optional[str], secret: str) -> Optional[Dict[str, Any]]:
    if not token or '.' not in token or not secret:
        return None
    encoded, signature = token.rsplit('.', 1)
    expected = _sign(encoded, secret)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_unb64(encoded).decode('utf-8'))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get('exp', 0)) < int(datetime.now(timezone.utc).timestamp()):
        return None
    return payload
