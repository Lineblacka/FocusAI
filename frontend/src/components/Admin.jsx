import { useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, BarChart3, Clock, Cpu, Database, Download, Eye, Gauge, Layers3,
  Lock, LogOut, MessageSquare, Monitor, RefreshCw, ShieldCheck, Smartphone, Sparkles,
  Tablet, Trash2, Users, Wifi,
} from 'lucide-react';
import {
  adminLogin, adminLogout, clearAdminAnalytics, exportAdminAnalytics, getAdminAnalytics, getAdminMe,
} from '../api/focusAiClient.js';

function formatNumber(value, suffix = '') {
  return `${new Intl.NumberFormat('bg-BG').format(Number(value || 0))}${suffix}`;
}

function formatDate(value) {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('bg-BG', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
  } catch { return value; }
}

function shortSession(value) {
  if (!value) return 'anonymous';
  return value.length > 22 ? `${value.slice(0, 12)}…${value.slice(-6)}` : value;
}

function DeviceIcon({ type }) {
  if (type === 'mobile') return <Smartphone size={17} />;
  if (type === 'tablet') return <Tablet size={17} />;
  return <Monitor size={17} />;
}

const KPI_CONFIG = [
  ['total_visits', 'Посещения', 'Входове към продукта', Eye],
  ['total_chat_sessions', 'Чат сесии', 'Стартирани активни сесии', Users],
  ['total_conversations_created', 'Нови чатове', 'Създадени разговори', MessageSquare],
  ['total_conversations_deleted', 'Изтрити чатове', 'Изчистени от потребители', Trash2],
  ['total_messages_sent', 'Съобщения', 'User prompts', Activity],
  ['total_ai_responses_generated', 'AI отговори', 'Успешни генерации', Sparkles],
  ['average_response_time', 'Средно време', 'Latency за AI отговор', Clock, 's'],
  ['failed_api_calls', 'Грешки', 'API / model failures', AlertTriangle],
  ['active_sessions_today', 'Активни днес', 'Уникални сесии за деня', BarChart3],
  ['rate_limit_events', 'Rate limits', 'Блокирани заявки', Gauge],
];

function MetricCard({ item, value }) {
  const [key, label, description, Icon, suffix] = item;
  const attention = (key === 'failed_api_calls' || key === 'rate_limit_events') && Number(value || 0) > 0;
  return (
    <article className={`admin-kpi-card ${attention ? 'attention' : ''}`}>
      <div className="admin-kpi-top">
        <div className="admin-kpi-icon"><Icon size={17} /></div>
        <span>{description}</span>
      </div>
      <div>
        <strong>{formatNumber(value, suffix || '')}</strong>
        <p>{label}</p>
      </div>
    </article>
  );
}

function DailyChart({ rows }) {
  const max = Math.max(...rows.map((row) => Number(row.messages || row.visits || row.responses || 0)), 1);
  return (
    <div className="admin-daily-chart">
      {rows.length ? rows.map((row) => {
        const visits = Number(row.visits || 0);
        const messages = Number(row.messages || 0);
        const responses = Number(row.responses || 0);
        const total = Math.max(visits, messages, responses);
        return (
          <div key={row.day} className="admin-day">
            <div className="admin-day-bars" title={`${row.day}: ${messages} messages`}>
              <span style={{ height: `${Math.max(8, (visits / max) * 100)}%` }} />
              <span style={{ height: `${Math.max(8, (messages / max) * 100)}%` }} />
              <span style={{ height: `${Math.max(8, (responses / max) * 100)}%` }} />
            </div>
            <small>{row.day.slice(5)}</small>
            <strong>{formatNumber(total)}</strong>
          </div>
        );
      }) : <div className="admin-empty">Все още няма дневни данни.</div>}
    </div>
  );
}

function DeviceBreakdown({ devices }) {
  const max = Math.max(...devices.map((item) => Number(item.sessions || 0)), 1);
  return (
    <div className="admin-device-list">
      {devices.length ? devices.map((item) => (
        <div key={item.device_type || 'unknown'} className="admin-device-item">
          <div className="admin-device-title">
            <span className="admin-device-name"><DeviceIcon type={item.device_type} />{item.device_type || 'unknown'}</span>
            <strong>{formatNumber(item.sessions)}</strong>
          </div>
          <div className="admin-device-bar"><div style={{ width: `${Math.max(7, (Number(item.sessions || 0) / max) * 100)}%` }} /></div>
          <small>{formatNumber(item.messages)} съобщения от този тип устройство</small>
        </div>
      )) : <div className="admin-empty">Няма отчетени устройства.</div>}
    </div>
  );
}

function downloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function AdminLogin() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [checking, setChecking] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getAdminMe().then(() => { window.location.assign('/admin/analytics'); }).catch(() => setChecking(false));
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      await adminLogin(username.trim(), password);
      window.location.assign('/admin/analytics');
    } catch (err) {
      setError(err.message || 'Невалидни данни за вход.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="admin-auth-shell">
      <section className="admin-login-card">
        <div className="admin-login-orb" aria-hidden="true" />
        <div className="admin-login-mark" aria-hidden="true" />
        <p className="admin-eyebrow">Private FocusAI admin</p>
        <h1>Analytics control room</h1>
        <p className="admin-login-copy">Скрит вътрешен панел за owner/developer метрики. Достъпът се валидира само през backend .env credentials.</p>
        <div className="admin-security-row">
          <span><Lock size={14} /> HttpOnly session</span>
          <span><ShieldCheck size={14} /> Backend protected</span>
        </div>
        {checking ? (
          <div className="admin-loading">Проверка на сесията…</div>
        ) : (
          <form className="admin-form" onSubmit={handleSubmit}>
            <label><span>Потребител</span><input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" /></label>
            <label><span>Парола</span><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /></label>
            {error ? <div className="admin-error">{error}</div> : null}
            <button type="submit" className="admin-primary" disabled={loading}>{loading ? 'Влизане…' : 'Влез в панела'}</button>
          </form>
        )}
      </section>
    </main>
  );
}

export function AdminDashboard() {
  const [data, setData] = useState(null);
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load({ silent = false } = {}) {
    if (!silent) setRefreshing(true);
    setError('');
    try {
      const me = await getAdminMe();
      const analytics = await getAdminAnalytics();
      setUsername(me.username);
      setData(analytics);
    } catch (err) {
      if ((err.message || '').includes('401') || (err.message || '').includes('Not authenticated')) {
        window.location.assign('/admin/login');
        return;
      }
      setError(err.message || 'Неуспешно зареждане на analytics.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load({ silent: true });
    const timer = window.setInterval(() => load({ silent: true }), 30000);
    return () => window.clearInterval(timer);
  }, []);

  async function logout() {
    await adminLogout();
    window.location.assign('/admin/login');
  }

  async function handleExport() {
    setNotice('');
    const payload = await exportAdminAnalytics();
    downloadJson(`focusai-analytics-${new Date().toISOString().slice(0, 10)}.json`, payload);
    setNotice('Export файлът е изтеглен.');
  }

  async function handleClear() {
    const ok = window.confirm('Сигурен ли си? Това ще изчисти analytics activity данните, но няма да пипа admin credentials.');
    if (!ok) return;
    await clearAdminAnalytics();
    setNotice('Analytics activity данните са изчистени.');
    await load();
  }

  const kpis = data?.kpis || {};
  const devices = data?.devices || [];
  const providers = data?.providers || [];
  const sessions = data?.recent_sessions || [];
  const errors = data?.recent_errors || [];
  const healthScore = Math.max(0, 100 - Number(kpis.failed_api_calls || 0) * 8 - Number(kpis.rate_limit_events || 0) * 3);
  const conversionHint = Number(kpis.total_visits || 0)
    ? Math.round((Number(kpis.total_messages_sent || 0) / Math.max(1, Number(kpis.total_visits || 1))) * 10) / 10
    : 0;

  if (loading) return <main className="admin-dashboard"><div className="admin-loading">Зареждане на dashboard…</div></main>;

  return (
    <main className="admin-dashboard">
      <header className="admin-hero">
        <div className="admin-hero-copy">
          <div className="admin-hero-badge"><ShieldCheck size={15} /> Private owner dashboard</div>
          <h1>FocusAI Analytics</h1>
          <p>Реални продуктови метрики, device breakdown, provider usage и developer diagnostics в UI, който не се показва никъде в нормалния продукт.</p>
          <div className="admin-hero-meta">
            <span><Wifi size={14} /> Live refresh 30s</span>
            <span><Database size={14} /> SQLite analytics store</span>
            <span><Users size={14} /> Admin: {username || 'admin'}</span>
          </div>
        </div>

        <div className="admin-actions-card">
          <div><span>Health score</span><strong>{formatNumber(healthScore)}%</strong><small>Базиран на recent errors и rate limits</small></div>
          <button type="button" className="admin-secondary" onClick={() => load()} disabled={refreshing}><RefreshCw size={16} className={refreshing ? 'admin-spin' : ''} />Обнови</button>
          <button type="button" className="admin-secondary" onClick={handleExport}><Download size={16} />Export JSON</button>
          <button type="button" className="admin-secondary danger" onClick={handleClear}><Trash2 size={16} />Clear activity</button>
          <button type="button" className="admin-secondary" onClick={logout}><LogOut size={16} />Изход</button>
        </div>
      </header>

      {error ? <div className="admin-error admin-error-wide">{error}</div> : null}
      {notice ? <div className="admin-notice">{notice}</div> : null}

      <section className="admin-insight-strip">
        <article><span>Messages / visit</span><strong>{formatNumber(conversionHint)}</strong><small>Бърз сигнал дали хората реално пишат след landing-а.</small></article>
        <article><span>AI success</span><strong>{formatNumber(kpis.total_ai_responses_generated)}</strong><small>Броят успешни отговори срещу грешки показва стабилност.</small></article>
        <article><span>Active today</span><strong>{formatNumber(kpis.active_sessions_today)}</strong><small>Най-полезната owner метрика за daily traction.</small></article>
      </section>

      <section className="admin-kpi-grid">
        {KPI_CONFIG.map((item) => <MetricCard key={item[0]} item={item} value={kpis[item[0]]} />)}
      </section>

      <section className="admin-grid">
        <article className="admin-panel admin-panel-large">
          <div className="admin-panel-head"><div><h2>Дневна употреба</h2><span>Visits / messages / AI responses за последните 14 дни</span></div><div className="admin-legend"><i /> visits <i /> messages <i /> responses</div></div>
          <DailyChart rows={data?.daily || []} />
        </article>

        <article className="admin-panel">
          <div className="admin-panel-head"><div><h2>Устройства</h2><span>Privacy-friendly client analytics</span></div></div>
          <DeviceBreakdown devices={devices} />
        </article>

        <article className="admin-panel">
          <div className="admin-panel-head"><div><h2>Models / providers</h2><span>Къде отиват заявките</span></div></div>
          <div className="admin-stat-list">
            {providers.length ? providers.map((item, index) => (
              <div key={item.provider} className="admin-stat-row"><span><Layers3 size={15} /> {index + 1}. {item.provider}</span><strong>{formatNumber(item.count)}</strong></div>
            )) : <div className="admin-empty">Няма provider данни.</div>}
          </div>
        </article>

        <article className="admin-panel">
          <div className="admin-panel-head"><div><h2>Developer checks</h2><span>Бърз operational snapshot</span></div></div>
          <div className="admin-check-list">
            <div><ShieldCheck size={16} /><span>Admin routes protected by backend cookie auth</span></div>
            <div><Lock size={16} /><span>Credentials stay in .env and never reach frontend</span></div>
            <div><Database size={16} /><span>Analytics stored separately from chat memory</span></div>
            <div><Gauge size={16} /><span>Login brute-force lockout enabled</span></div>
          </div>
        </article>

        <article className="admin-panel admin-panel-large">
          <div className="admin-panel-head"><div><h2>Последни сесии</h2><span>Browser, OS, screen size, messages, visits</span></div></div>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead><tr><th>Session</th><th>Device</th><th>Browser</th><th>OS</th><th>Screen</th><th>First seen</th><th>Last seen</th><th>Visits</th><th>Msgs</th></tr></thead>
              <tbody>
                {sessions.length ? sessions.map((row) => (
                  <tr key={row.session_id}>
                    <td><code>{shortSession(row.session_id)}</code></td><td>{row.device_type || '—'}</td><td>{row.browser || '—'} {row.browser_version || ''}</td><td>{row.os || '—'}</td><td>{row.screen_size || '—'}</td><td>{formatDate(row.first_seen)}</td><td>{formatDate(row.last_seen)}</td><td>{formatNumber(row.visits)}</td><td>{formatNumber(row.messages)}</td>
                  </tr>
                )) : <tr><td colSpan="9">Няма активни сесии.</td></tr>}
              </tbody>
            </table>
          </div>
        </article>

        <article className="admin-panel admin-panel-large">
          <div className="admin-panel-head"><div><h2>Последни грешки</h2><span>API failures и системни проблеми</span></div></div>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead><tr><th>Time</th><th>Source</th><th>Status</th><th>Message</th></tr></thead>
              <tbody>
                {errors.length ? errors.map((row) => (
                  <tr key={`${row.created_at}-${row.message}`}><td>{formatDate(row.created_at)}</td><td>{row.source}</td><td>{row.status_code || '—'}</td><td>{row.message}</td></tr>
                )) : <tr><td colSpan="4">Няма записани грешки. Добър знак.</td></tr>}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </main>
  );
}