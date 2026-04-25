from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default='default', min_length=1, max_length=128)
    mode: str = Field(default='normal')
    web_search: str = Field(default='auto')

    @field_validator('message')
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('message cannot be empty')
        return cleaned

    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('session_id cannot be empty')
        return cleaned

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {'normal', 'brutal'}:
            raise ValueError('mode must be "normal" or "brutal"')
        return cleaned

    @field_validator('web_search')
    @classmethod
    def validate_web_search(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {'auto', 'on', 'off'}:
            raise ValueError('web_search must be "auto", "on", or "off"')
        return cleaned


class ChatResponse(BaseModel):
    reply: str
    model: Optional[str]
    latency_seconds: Optional[float]
    intent: str
    quality: Dict[str, Any]
    sources: List[Dict[str, str]] = []


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=1000)
    session_id: str = Field(default='default', min_length=1, max_length=128)

    @field_validator('command', 'session_id')
    @classmethod
    def validate_command_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('field cannot be empty')
        return cleaned


class CommandResponse(BaseModel):
    ok: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    models: List[str]
