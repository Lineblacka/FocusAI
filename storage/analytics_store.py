import ipaddress
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utc_now().isoformat(timespec='seconds')


def today_key() -> str:
    return utc_now().date().isoformat()


def safe_text(value: Any, limit: int = 500) -> str:
    if value is None:
        return ''
    return str(value).strip()[:limit]


def _is_private_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def _display_ip(value: str) -> str:
    ip = safe_text(value, 80) or 'unknown'
    return ip


def _country_from_ip(ip: str, country_code: str, source: str) -> tuple[str, str]:
    code = safe_text(country_code, 8).upper()
    if code and code not in {'XX', 'T1'}:
        return code[:8], safe_text(source or 'proxy_header', 40)
    if _is_private_ip(ip):
        return 'LOCAL', 'private_network'
    return 'UNKNOWN', 'not_available'


def infer_device_name(device: Dict[str, Any]) -> str:
    explicit = safe_text(device.get('device_name') or device.get('deviceName'), 80)
    if explicit:
        return explicit
    ua = safe_text(device.get('user_agent') or device.get('userAgent'), 500)
    os_name = safe_text(device.get('os'), 80)
    dtype = safe_text(device.get('device_type') or device.get('deviceType'), 40)
    if 'iPad' in ua:
        return 'iPad'
    if 'iPhone' in ua:
        return 'iPhone'
    if 'Android' in ua and 'Mobile' in ua:
        return 'Android Phone'
    if 'Android' in ua:
        return 'Android Tablet'
    if os_name == 'macOS':
        return 'Mac'
    if os_name == 'Windows':
        return 'Windows PC'
    if os_name == 'Linux':
        return 'Linux PC'
    if dtype == 'mobile':
        return 'Mobile Device'
    if dtype == 'tablet':
        return 'Tablet'
    return 'Desktop PC'


class AnalyticsStore:
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
                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS daily_metrics (
                    day TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(day, name)
                );

                CREATE TABLE IF NOT EXISTS response_times (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    latency_seconds REAL NOT NULL,
                    model TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS provider_usage (
                    provider TEXT PRIMARY KEY,
                    count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS device_sessions (
                    session_id TEXT PRIMARY KEY,
                    device_type TEXT,
                    device_name TEXT,
                    browser TEXT,
                    browser_version TEXT,
                    os TEXT,
                    screen_size TEXT,
                    viewport_size TEXT,
                    language TEXT,
                    user_agent TEXT,
                    ip TEXT,
                    country_code TEXT,
                    country_source TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    visits INTEGER NOT NULL DEFAULT 0,
                    messages INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS recent_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status_code INTEGER,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_login_attempts (
                    ip TEXT PRIMARY KEY,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    last_failed_at TEXT
                );

                '''
            )

            # Lightweight migration for existing local analytics.sqlite3 files.
            # Run this before creating indexes that reference newly added columns.
            existing = {row['name'] for row in conn.execute('PRAGMA table_info(device_sessions)').fetchall()}
            for name, decl in {
                'device_type': 'TEXT',
                'device_name': 'TEXT',
                'browser': 'TEXT',
                'browser_version': 'TEXT',
                'os': 'TEXT',
                'screen_size': 'TEXT',
                'viewport_size': 'TEXT',
                'language': 'TEXT',
                'user_agent': 'TEXT',
                'ip': 'TEXT',
                'country_code': 'TEXT',
                'country_source': 'TEXT',
                'first_seen': 'TEXT',
                'last_seen': 'TEXT',
                'visits': 'INTEGER NOT NULL DEFAULT 0',
                'messages': 'INTEGER NOT NULL DEFAULT 0',
            }.items():
                if name not in existing:
                    conn.execute(f'ALTER TABLE device_sessions ADD COLUMN {name} {decl}')

            conn.executescript(
                '''
                CREATE INDEX IF NOT EXISTS idx_response_times_created ON response_times(created_at);
                CREATE INDEX IF NOT EXISTS idx_recent_errors_created ON recent_errors(created_at);
                CREATE INDEX IF NOT EXISTS idx_device_sessions_last_seen ON device_sessions(last_seen);
                CREATE INDEX IF NOT EXISTS idx_device_sessions_ip ON device_sessions(ip);
                '''
            )
            conn.commit()

    def increment(self, name: str, amount: int = 1, day: Optional[str] = None) -> None:
        day = day or today_key()
        with self.lock, self._connect() as conn:
            conn.execute(
                '''
                INSERT INTO counters(name, value) VALUES(?, ?)
                ON CONFLICT(name) DO UPDATE SET value = value + excluded.value
                ''',
                (name, amount),
            )
            conn.execute(
                '''
                INSERT INTO daily_metrics(day, name, value) VALUES(?, ?, ?)
                ON CONFLICT(day, name) DO UPDATE SET value = value + excluded.value
                ''',
                (day, name, amount),
            )
            conn.commit()

    def _increment_conn(self, conn: sqlite3.Connection, name: str, amount: int = 1) -> None:
        day = today_key()
        conn.execute(
            '''
            INSERT INTO counters(name, value) VALUES(?, ?)
            ON CONFLICT(name) DO UPDATE SET value = value + excluded.value
            ''',
            (name, amount),
        )
        conn.execute(
            '''
            INSERT INTO daily_metrics(day, name, value) VALUES(?, ?, ?)
            ON CONFLICT(day, name) DO UPDATE SET value = value + excluded.value
            ''',
            (day, name, amount),
        )

    def track_visit(self, session_id: str, device: Dict[str, Any], request_meta: Optional[Dict[str, Any]] = None) -> None:
        meta = request_meta or {}
        sid = safe_text(session_id, 160) or 'anonymous'
        timestamp = now_iso()
        device_type = safe_text(device.get('device_type') or device.get('deviceType'), 40) or 'unknown'
        device_name = infer_device_name(device)
        browser = safe_text(device.get('browser'), 80) or 'unknown'
        browser_version = safe_text(device.get('browser_version') or device.get('browserVersion'), 40)
        os_name = safe_text(device.get('os'), 80) or 'unknown'
        screen_size = safe_text(device.get('screen_size') or device.get('screenSize'), 40)
        viewport_size = safe_text(device.get('viewport_size') or device.get('viewportSize'), 40)
        language = safe_text(device.get('language'), 40)
        user_agent = safe_text(device.get('user_agent') or device.get('userAgent'), 500)
        ip = _display_ip(meta.get('ip'))
        country_code, country_source = _country_from_ip(ip, meta.get('country_code', ''), meta.get('country_source', ''))

        with self.lock, self._connect() as conn:
            existing = conn.execute('SELECT session_id FROM device_sessions WHERE session_id = ?', (sid,)).fetchone()
            if existing:
                conn.execute(
                    '''
                    UPDATE device_sessions
                    SET device_type = ?, device_name = ?, browser = ?, browser_version = ?, os = ?, screen_size = ?,
                        viewport_size = ?, language = ?, user_agent = ?, ip = ?, country_code = ?, country_source = ?,
                        last_seen = ?, visits = visits + 1
                    WHERE session_id = ?
                    ''',
                    (device_type, device_name, browser, browser_version, os_name, screen_size, viewport_size, language,
                     user_agent, ip, country_code, country_source, timestamp, sid),
                )
            else:
                conn.execute(
                    '''
                    INSERT INTO device_sessions(
                        session_id, device_type, device_name, browser, browser_version, os, screen_size,
                        viewport_size, language, user_agent, ip, country_code, country_source,
                        first_seen, last_seen, visits, messages
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
                    ''',
                    (sid, device_type, device_name, browser, browser_version, os_name, screen_size, viewport_size,
                     language, user_agent, ip, country_code, country_source, timestamp, timestamp),
                )
            self._increment_conn(conn, 'total_visits')
            self._increment_conn(conn, 'active_sessions')
            conn.commit()

    def track_message(self, session_id: str, model: Optional[str], latency_seconds: Optional[float], ok: bool = True) -> None:
        timestamp = now_iso()
        provider = safe_text(model or 'shortcut', 160) or 'unknown'
        with self.lock, self._connect() as conn:
            self._increment_conn(conn, 'total_messages_sent')
            if ok:
                self._increment_conn(conn, 'total_ai_responses_generated')
            sid = safe_text(session_id, 160)
            if sid:
                conn.execute('UPDATE device_sessions SET messages = messages + 1, last_seen = ? WHERE session_id = ?', (timestamp, sid.split(':')[0]))
            if latency_seconds is not None:
                conn.execute(
                    'INSERT INTO response_times(latency_seconds, model, created_at) VALUES(?, ?, ?)',
                    (float(latency_seconds), provider, timestamp),
                )
            conn.execute(
                '''
                INSERT INTO provider_usage(provider, count) VALUES(?, 1)
                ON CONFLICT(provider) DO UPDATE SET count = count + 1
                ''',
                (provider,),
            )
            conn.commit()

    def track_event(self, event: str, session_id: str = '', device: Optional[Dict[str, Any]] = None, request_meta: Optional[Dict[str, Any]] = None) -> None:
        event_map = {
            'visit': 'total_visits',
            'chat_session': 'total_chat_sessions',
            'conversation_created': 'total_conversations_created',
            'conversation_deleted': 'total_conversations_deleted',
            'rate_limit': 'rate_limit_events',
        }
        if event == 'visit':
            self.track_visit(session_id, device or {}, request_meta=request_meta)
            return
        metric = event_map.get(event)
        if metric:
            self.increment(metric)

    def track_error(self, source: str, message: str, status_code: Optional[int] = None) -> None:
        with self.lock, self._connect() as conn:
            self._increment_conn(conn, 'failed_api_calls')
            conn.execute(
                'INSERT INTO recent_errors(source, message, status_code, created_at) VALUES(?, ?, ?, ?)',
                (safe_text(source, 120) or 'api', safe_text(message, 600) or 'Unknown error', status_code, now_iso()),
            )
            conn.commit()

    def is_login_locked(self, ip: str) -> tuple[bool, Optional[str]]:
        with self.lock, self._connect() as conn:
            row = conn.execute('SELECT locked_until FROM admin_login_attempts WHERE ip = ?', (ip,)).fetchone()
            if not row or not row['locked_until']:
                return False, None
            try:
                locked_until = datetime.fromisoformat(row['locked_until'])
            except ValueError:
                return False, None
            if locked_until > utc_now():
                return True, row['locked_until']
            conn.execute('UPDATE admin_login_attempts SET failed_count = 0, locked_until = NULL WHERE ip = ?', (ip,))
            conn.commit()
            return False, None

    def record_login_success(self, ip: str) -> None:
        with self.lock, self._connect() as conn:
            conn.execute('DELETE FROM admin_login_attempts WHERE ip = ?', (ip,))
            conn.commit()

    def record_login_failure(self, ip: str, max_failures: int = 5, lockout_minutes: int = 15) -> Optional[str]:
        timestamp = now_iso()
        with self.lock, self._connect() as conn:
            row = conn.execute('SELECT failed_count FROM admin_login_attempts WHERE ip = ?', (ip,)).fetchone()
            failed_count = (int(row['failed_count']) if row else 0) + 1
            locked_until = None
            if failed_count >= max_failures:
                locked_until = (utc_now() + timedelta(minutes=lockout_minutes)).isoformat(timespec='seconds')
            conn.execute(
                '''
                INSERT INTO admin_login_attempts(ip, failed_count, locked_until, last_failed_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    failed_count = excluded.failed_count,
                    locked_until = excluded.locked_until,
                    last_failed_at = excluded.last_failed_at
                ''',
                (ip, failed_count, locked_until, timestamp),
            )
            conn.commit()
            return locked_until

    def summary(self) -> Dict[str, Any]:
        since_14d = (utc_now() - timedelta(days=13)).date().isoformat()
        today_start = utc_now().date().isoformat()
        with self.lock, self._connect() as conn:
            counters = {row['name']: row['value'] for row in conn.execute('SELECT name, value FROM counters')}
            avg_row = conn.execute('SELECT AVG(latency_seconds) AS avg_latency FROM response_times').fetchone()
            active_today = conn.execute('SELECT COUNT(*) AS count FROM device_sessions WHERE last_seen >= ?', (today_start,)).fetchone()['count']
            daily_rows = conn.execute(
                '''
                SELECT day,
                    SUM(CASE WHEN name = 'total_visits' THEN value ELSE 0 END) AS visits,
                    SUM(CASE WHEN name = 'total_messages_sent' THEN value ELSE 0 END) AS messages,
                    SUM(CASE WHEN name = 'total_ai_responses_generated' THEN value ELSE 0 END) AS responses,
                    SUM(CASE WHEN name = 'failed_api_calls' THEN value ELSE 0 END) AS errors
                FROM daily_metrics
                WHERE day >= ?
                GROUP BY day
                ORDER BY day ASC
                ''',
                (since_14d,),
            ).fetchall()
            device_rows = conn.execute(
                '''
                SELECT device_type, COUNT(*) AS sessions, COALESCE(SUM(messages), 0) AS messages
                FROM device_sessions
                GROUP BY device_type
                ORDER BY sessions DESC
                '''
            ).fetchall()
            device_profile_rows = conn.execute(
                '''
                SELECT device_name, os, browser, COUNT(*) AS sessions, COALESCE(SUM(messages), 0) AS messages,
                       MAX(last_seen) AS last_seen
                FROM device_sessions
                GROUP BY device_name, os, browser
                ORDER BY sessions DESC, messages DESC
                LIMIT 12
                '''
            ).fetchall()
            ip_rows = conn.execute(
                '''
                SELECT ip, country_code, country_source, COUNT(*) AS sessions, COALESCE(SUM(visits), 0) AS visits,
                       COALESCE(SUM(messages), 0) AS messages, MAX(last_seen) AS last_seen
                FROM device_sessions
                WHERE ip IS NOT NULL AND ip != ''
                GROUP BY ip, country_code, country_source
                ORDER BY last_seen DESC
                LIMIT 20
                '''
            ).fetchall()
            provider_rows = conn.execute('SELECT provider, count FROM provider_usage ORDER BY count DESC LIMIT 8').fetchall()
            error_rows = conn.execute('SELECT source, message, status_code, created_at FROM recent_errors ORDER BY id DESC LIMIT 10').fetchall()
            session_rows = conn.execute(
                '''
                SELECT session_id, device_type, device_name, browser, browser_version, os, screen_size, viewport_size,
                       language, ip, country_code, country_source, first_seen, last_seen, visits, messages
                FROM device_sessions
                ORDER BY last_seen DESC
                LIMIT 20
                '''
            ).fetchall()

        return {
            'kpis': {
                'total_visits': counters.get('total_visits', 0),
                'total_chat_sessions': counters.get('total_chat_sessions', 0),
                'total_conversations_created': counters.get('total_conversations_created', 0),
                'total_conversations_deleted': counters.get('total_conversations_deleted', 0),
                'total_messages_sent': counters.get('total_messages_sent', 0),
                'total_ai_responses_generated': counters.get('total_ai_responses_generated', 0),
                'average_response_time': round(float(avg_row['avg_latency'] or 0), 2),
                'failed_api_calls': counters.get('failed_api_calls', 0),
                'active_sessions_today': active_today,
                'rate_limit_events': counters.get('rate_limit_events', 0),
            },
            'daily': [dict(row) for row in daily_rows],
            'devices': [dict(row) for row in device_rows],
            'device_profiles': [dict(row) for row in device_profile_rows],
            'ip_summary': [dict(row) for row in ip_rows],
            'providers': [dict(row) for row in provider_rows],
            'recent_errors': [dict(row) for row in error_rows],
            'recent_sessions': [dict(row) for row in session_rows],
            'generated_at': now_iso(),
        }

    def export_all(self) -> Dict[str, Any]:
        with self.lock, self._connect() as conn:
            def rows(query: str, params: tuple = ()) -> list[Dict[str, Any]]:
                return [dict(row) for row in conn.execute(query, params).fetchall()]

            return {
                'summary': self.summary(),
                'counters': rows('SELECT name, value FROM counters ORDER BY name'),
                'daily_metrics': rows('SELECT day, name, value FROM daily_metrics ORDER BY day DESC, name'),
                'devices': rows('SELECT * FROM device_sessions ORDER BY last_seen DESC'),
                'providers': rows('SELECT provider, count FROM provider_usage ORDER BY count DESC'),
                'response_times': rows('SELECT latency_seconds, model, created_at FROM response_times ORDER BY created_at DESC LIMIT 500'),
                'recent_errors': rows('SELECT source, message, status_code, created_at FROM recent_errors ORDER BY id DESC LIMIT 500'),
                'exported_at': now_iso(),
            }

    def clear_activity(self) -> None:
        with self.lock, self._connect() as conn:
            conn.executescript('''
                DELETE FROM counters;
                DELETE FROM daily_metrics;
                DELETE FROM response_times;
                DELETE FROM provider_usage;
                DELETE FROM device_sessions;
                DELETE FROM recent_errors;
            ''')
            conn.commit()
