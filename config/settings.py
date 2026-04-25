from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = Field(default='FocusAI', alias='APP_NAME')
    app_env: str = Field(default='dev', alias='APP_ENV')
    openrouter_api_key: str = Field(alias='OPENROUTER_API_KEY')
    openrouter_base_url: str = Field(default='https://openrouter.ai/api/v1', alias='OPENROUTER_BASE_URL')
    openrouter_models_csv: str = Field(default='openai/gpt-oss-20b:free', alias='OPENROUTER_MODELS')
    cors_origins_csv: str = Field(default='http://localhost:5173,http://127.0.0.1:5173', alias='CORS_ORIGINS')
    allowed_hosts_csv: str = Field(default='localhost,127.0.0.1', alias='ALLOWED_HOSTS')
    trusted_proxies_csv: str = Field(default='', alias='TRUSTED_PROXIES')
    data_dir: Path = Field(default=Path('./data'), alias='DATA_DIR')
    request_timeout_seconds: int = Field(default=90, alias='REQUEST_TIMEOUT_SECONDS')
    empty_reply_retries: int = Field(default=2, alias='EMPTY_REPLY_RETRIES')
    model_temperature: float = Field(default=0.4, alias='MODEL_TEMPERATURE')
    max_history_messages: int = Field(default=16, alias='MAX_HISTORY_MESSAGES')
    rate_limit_per_minute: int = Field(default=60, alias='RATE_LIMIT_PER_MINUTE')
    max_request_bytes: int = Field(default=65536, alias='MAX_REQUEST_BYTES')
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')

    @field_validator('openrouter_api_key')
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        if not value or value == 'your_openrouter_api_key_here':
            raise ValueError('OPENROUTER_API_KEY is required')
        return value

    @property
    def openrouter_models(self) -> List[str]:
        raw = self.openrouter_models_csv.strip()
        if raw.startswith('[') and raw.endswith(']'):
            import json

            parsed = json.loads(raw)
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in raw.split(',') if item.strip()]

    @property
    def cors_origins(self) -> List[str]:
        return [item.strip() for item in self.cors_origins_csv.split(',') if item.strip()]

    @property
    def allowed_hosts(self) -> List[str]:
        return [item.strip() for item in self.allowed_hosts_csv.split(',') if item.strip()]

    @property
    def trusted_proxies(self) -> List[str]:
        return [item.strip() for item in self.trusted_proxies_csv.split(',') if item.strip()]

    @property
    def memory_path(self) -> Path:
        return self.data_dir / 'memory.sqlite3'

    @property
    def rate_limit_path(self) -> Path:
        return self.data_dir / 'rate_limit.sqlite3'

    @property
    def benchmark_path(self) -> Path:
        return self.data_dir / 'benchmark_cases.json'

    @property
    def benchmark_results_path(self) -> Path:
        return self.data_dir / 'benchmark_results.json'


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
