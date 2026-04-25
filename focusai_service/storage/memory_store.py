import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.prompts import PROMPT_VERSION


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def default_memory() -> Dict[str, Any]:
    return {
        'profile': {
            'goals': [],
            'bad_patterns': [],
            'commitments': [],
            'preferred_style': 'strict',
        },
        'messages': [],
        'sessions': {},
        'stats': {
            'total_messages': 0,
            'last_model': None,
            'prompt_version': PROMPT_VERSION,
        },
        'last_updated': now_iso(),
    }


class MemoryStore:
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
                CREATE TABLE IF NOT EXISTS profile_items (
                    category TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY (category, value)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT,
                    latency_seconds REAL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                '''
            )
            conn.execute(
                '''
                INSERT INTO meta(key, value) VALUES('preferred_style', ?)
                ON CONFLICT(key) DO NOTHING
                ''',
                ('strict',),
            )
            conn.execute(
                '''
                INSERT INTO meta(key, value) VALUES('prompt_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                ''',
                (PROMPT_VERSION,),
            )

    def _meta(self, conn: sqlite3.Connection, key: str, fallback: str | None = None) -> str | None:
        row = conn.execute('SELECT value FROM meta WHERE key = ?', (key,)).fetchone()
        return row['value'] if row else fallback

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            '''
            INSERT INTO meta(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            ''',
            (key, value),
        )

    def _profile(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        profile = default_memory()['profile']
        rows = conn.execute(
            'SELECT category, value FROM profile_items ORDER BY rowid ASC'
        ).fetchall()
        for row in rows:
            profile.setdefault(row['category'], []).append(row['value'])
        profile['preferred_style'] = self._meta(conn, 'preferred_style', 'strict') or 'strict'
        return profile

    def _stats(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        total_messages = conn.execute('SELECT COUNT(*) AS count FROM messages').fetchone()['count']
        last_model_row = conn.execute(
            '''
            SELECT model
            FROM messages
            WHERE role = 'assistant' AND model IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            '''
        ).fetchone()
        return {
            'total_messages': total_messages,
            'last_model': last_model_row['model'] if last_model_row else None,
            'prompt_version': self._meta(conn, 'prompt_version', PROMPT_VERSION) or PROMPT_VERSION,
        }

    def _session_messages(self, conn: sqlite3.Connection, session_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            '''
            SELECT role, content, model, latency_seconds, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            ''',
            (session_id,),
        ).fetchall()
        return [
            {
                'role': row['role'],
                'content': row['content'],
                'model': row['model'],
                'latency_seconds': row['latency_seconds'],
                'created_at': row['created_at'],
            }
            for row in rows
        ]

    def load(self) -> Dict[str, Any]:
        with self.lock, self._connect() as conn:
            memory = default_memory()
            memory['profile'] = self._profile(conn)
            memory['stats'] = self._stats(conn)
            memory['last_updated'] = self._meta(conn, 'last_updated', now_iso()) or now_iso()

            session_rows = conn.execute(
                '''
                SELECT session_id, MIN(created_at) AS created_at, MAX(created_at) AS updated_at
                FROM messages
                GROUP BY session_id
                ORDER BY updated_at DESC
                '''
            ).fetchall()
            sessions: Dict[str, Any] = {}
            for row in session_rows:
                sessions[row['session_id']] = {'messages': self._session_messages(conn, row['session_id'])}
            memory['sessions'] = sessions
            memory['messages'] = sessions.get('default', {}).get('messages', [])
            return memory

    def load_session(self, session_id: str) -> Dict[str, Any]:
        with self.lock, self._connect() as conn:
            return {
                'profile': self._profile(conn),
                'messages': self._session_messages(conn, session_id),
                'stats': self._stats(conn),
                'last_updated': self._meta(conn, 'last_updated', now_iso()) or now_iso(),
            }

    def save(self, memory: Dict[str, Any]) -> None:
        with self.lock, self._connect() as conn:
            self._set_meta(conn, 'last_updated', now_iso())
            self._set_meta(conn, 'prompt_version', PROMPT_VERSION)

    def append_turn(self, user_input: str, reply: str, model: str | None, latency: float | None, session_id: str = 'default') -> None:
        timestamp = now_iso()
        with self.lock, self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute(
                '''
                INSERT INTO messages(session_id, role, content, model, latency_seconds, created_at)
                VALUES(?, 'user', ?, NULL, NULL, ?)
                ''',
                (session_id, user_input, timestamp),
            )
            conn.execute(
                '''
                INSERT INTO messages(session_id, role, content, model, latency_seconds, created_at)
                VALUES(?, 'assistant', ?, ?, ?, ?)
                ''',
                (session_id, reply, model, latency, timestamp),
            )
            self._set_meta(conn, 'last_updated', timestamp)
            self._set_meta(conn, 'prompt_version', PROMPT_VERSION)
            conn.commit()

    def add_profile_item(self, category: str, value: str) -> bool:
        allowed = {'goals', 'bad_patterns', 'commitments'}
        if category not in allowed:
            raise ValueError(f'Invalid category: {category}')

        value = value.strip()
        if not value:
            return False

        with self.lock, self._connect() as conn:
            result = conn.execute(
                '''
                INSERT OR IGNORE INTO profile_items(category, value)
                VALUES(?, ?)
                ''',
                (category, value),
            )
            inserted = result.rowcount > 0
            if inserted:
                self._set_meta(conn, 'last_updated', now_iso())
            return inserted
