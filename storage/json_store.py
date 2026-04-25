import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class JsonStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self, fallback: Any) -> Any:
        with self.lock:
            if not self.path.exists():
                return fallback
            try:
                content = self.path.read_text(encoding='utf-8').strip()
                if not content:
                    return fallback
                return json.loads(content)
            except json.JSONDecodeError:
                logger.warning('json_store_corrupt path=%s', self.path)
                return fallback
            except OSError as exc:
                logger.error('json_store_read_error path=%s error=%s', self.path, exc)
                return fallback

    def write(self, data: Any) -> None:
        with self.lock:
            tmp = self.path.with_suffix(self.path.suffix + '.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            tmp.replace(self.path)
