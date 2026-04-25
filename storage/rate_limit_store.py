import sqlite3
import threading
import time
from pathlib import Path


class RateLimitStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn

    def _init_db(self) -> None:
        with self.lock, self._connect() as conn:
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS rate_limit_hits (
                    client_key TEXT NOT NULL,
                    hit_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rate_limit_hits_key_time
                ON rate_limit_hits(client_key, hit_at);
                '''
            )

    def check_and_record(self, client_key: str, limit_per_minute: int) -> bool:
        now = time.time()
        window_start = now - 60

        with self.lock, self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('DELETE FROM rate_limit_hits WHERE hit_at < ?', (window_start,))
            count = conn.execute(
                'SELECT COUNT(*) AS count FROM rate_limit_hits WHERE client_key = ? AND hit_at >= ?',
                (client_key, window_start),
            ).fetchone()['count']
            if count >= limit_per_minute:
                conn.commit()
                return False

            conn.execute(
                'INSERT INTO rate_limit_hits(client_key, hit_at) VALUES(?, ?)',
                (client_key, now),
            )
            conn.commit()
            return True
