(function(){
  const app = document.getElementById('app');
  let lastData = null;

  const fmt = (value, suffix = '') => {
    const n = Number(value || 0);
    return Number.isFinite(n) ? n.toLocaleString('bg-BG') + suffix : String(value || '0');
  };
  const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const short = (value, left = 10, right = 6) => {
    const s = String(value || '');
    return s.length > left + right + 1 ? `${s.slice(0,left)}…${s.slice(-right)}` : (s || '—');
  };
  const dateFmt = (value) => value ? new Date(value).toLocaleString('bg-BG', { dateStyle: 'short', timeStyle: 'short' }) : '—';
  const since = (value) => {
    if (!value) return '—';
    const diff = Date.now() - new Date(value).getTime();
    if (!Number.isFinite(diff)) return dateFmt(value);
    const min = Math.floor(diff / 60000);
    if (min < 1) return 'just now';
    if (min < 60) return `${min}m ago`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  };

  async function api(path, opts = {}) {
    const response = await fetch(path, { credentials: 'include', headers: { 'Content-Type': 'application/json' }, ...opts });
    if (response.status === 401) {
      window.location.href = '/admin/login';
      throw new Error('unauthorized');
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  function downloadJson(name, obj) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function countryFlag(code) {
    const c = String(code || '').toUpperCase();
    if (c === 'LOCAL') return '🏠';
    if (!/^[A-Z]{2}$/.test(c)) return '🌐';
    return c.replace(/./g, ch => String.fromCodePoint(127397 + ch.charCodeAt(0)));
  }

  function countryLabel(code, source) {
    const c = String(code || '').toUpperCase();
    if (c === 'LOCAL') return 'Local network';
    if (c === 'UNKNOWN' || !c) return 'Unknown country';
    return `${countryFlag(c)} ${esc(c)}${source ? ` · ${esc(source)}` : ''}`;
  }

  function deviceIcon(name, type, os) {
    const text = `${name || ''} ${type || ''} ${os || ''}`.toLowerCase();
    if (text.includes('iphone') || text.includes('android phone') || text.includes('mobile')) return '📱';
    if (text.includes('ipad') || text.includes('tablet')) return '▭';
    if (text.includes('mac')) return '';
    if (text.includes('windows') || text.includes('pc') || text.includes('desktop')) return '🖥️';
    return '💻';
  }

  function healthScore(k) {
    const errors = Number(k.failed_api_calls || 0);
    const limits = Number(k.rate_limit_events || 0);
    const totalResponses = Number(k.total_ai_responses_generated || 0);
    const penalty = errors * 8 + limits * 3;
    const base = Math.max(0, 100 - penalty);
    return totalResponses ? base : Math.min(base, 95);
  }

  function empty(text) {
    return `<div class="empty">${esc(text)}</div>`;
  }

  function kpiCard(label, value, help, suffix = '') {
    return `<article class="card kpi"><span>${esc(help)}</span><strong>${fmt(value, suffix)}</strong><small>${esc(label)}</small></article>`;
  }

  function drawBars(daily) {
    if (!daily.length) return empty('No daily usage yet. Data appears after real visits/messages.');
    const max = Math.max(...daily.map(r => Math.max(Number(r.visits || 0), Number(r.messages || 0), Number(r.responses || 0))), 1);
    return `<div class="chart">${daily.map(r => `
      <div class="day" title="${esc(r.day)}">
        <div class="bars">
          <span class="bar visits" style="height:${Math.max(5, Number(r.visits || 0) / max * 100)}%"></span>
          <span class="bar messages" style="height:${Math.max(5, Number(r.messages || 0) / max * 100)}%"></span>
          <span class="bar responses" style="height:${Math.max(5, Number(r.responses || 0) / max * 100)}%"></span>
        </div>
        <small>${esc(String(r.day || '').slice(5))}</small>
      </div>`).join('')}</div>`;
  }

  function progressList(items, valueKey, render) {
    if (!items.length) return empty('No data yet.');
    const max = Math.max(...items.map(i => Number(i[valueKey] || 0)), 1);
    return `<div class="list">${items.map(item => {
      const value = Number(item[valueKey] || 0);
      return `<div>${render(item)}<div class="meter"><div style="width:${Math.max(5, value / max * 100)}%"></div></div></div>`;
    }).join('')}</div>`;
  }

  function sessionsTable(sessions) {
    if (!sessions.length) return empty('No sessions recorded yet.');
    return `<div class="table-wrap"><table><thead><tr>
      <th>Session</th><th>Device</th><th>Browser</th><th>OS</th><th>IP / country</th><th>Screen</th><th>Language</th><th>Last seen</th><th>Visits</th><th>Msgs</th>
    </tr></thead><tbody>${sessions.map(s => `
      <tr>
        <td><code>${esc(short(s.session_id))}</code></td>
        <td><strong>${deviceIcon(s.device_name, s.device_type, s.os)} ${esc(s.device_name || s.device_type || 'Unknown')}</strong><br><span class="muted">${esc(s.device_type || '—')}</span></td>
        <td>${esc(s.browser || '—')} ${esc(s.browser_version || '')}</td>
        <td>${esc(s.os || '—')}</td>
        <td><code>${esc(s.ip || 'unknown')}</code><br><span class="muted">${countryLabel(s.country_code, s.country_source)}</span></td>
        <td>${esc(s.screen_size || '—')}${s.viewport_size ? `<br><span class="muted">viewport ${esc(s.viewport_size)}</span>` : ''}</td>
        <td>${esc(s.language || '—')}</td>
        <td class="nowrap">${esc(since(s.last_seen))}<br><span class="muted">${esc(dateFmt(s.last_seen))}</span></td>
        <td>${fmt(s.visits)}</td><td>${fmt(s.messages)}</td>
      </tr>`).join('')}</tbody></table></div>`;
  }

  function ipTable(rows) {
    if (!rows.length) return empty('No IP records yet.');
    return `<div class="table-wrap"><table><thead><tr><th>IP</th><th>Country</th><th>Sessions</th><th>Visits</th><th>Messages</th><th>Last seen</th></tr></thead><tbody>${rows.map(r => `
      <tr><td><code>${esc(r.ip || 'unknown')}</code></td><td>${countryLabel(r.country_code, r.country_source)}</td><td>${fmt(r.sessions)}</td><td>${fmt(r.visits)}</td><td>${fmt(r.messages)}</td><td>${esc(since(r.last_seen))}</td></tr>
    `).join('')}</tbody></table></div>`;
  }

  function errorsTable(errors) {
    if (!errors.length) return empty('No backend/model errors recorded.');
    return `<div class="table-wrap"><table><thead><tr><th>Time</th><th>Source</th><th>Status</th><th>Message</th></tr></thead><tbody>${errors.map(e => `
      <tr><td class="nowrap">${esc(dateFmt(e.created_at))}</td><td>${esc(e.source)}</td><td>${esc(e.status_code || '—')}</td><td>${esc(e.message)}</td></tr>
    `).join('')}</tbody></table></div>`;
  }

  function render(me, data) {
    lastData = data;
    const k = data.kpis || {};
    const daily = data.daily || [];
    const devices = data.devices || [];
    const profiles = data.device_profiles || [];
    const ipRows = data.ip_summary || [];
    const providers = data.providers || [];
    const sessions = data.recent_sessions || [];
    const errors = data.recent_errors || [];
    const health = healthScore(k);
    const responseSuccess = Number(k.total_messages_sent || 0) ? Math.round(Number(k.total_ai_responses_generated || 0) / Number(k.total_messages_sent || 1) * 100) : 0;
    const messagesPerSession = Number(k.total_chat_sessions || 0) ? Math.round(Number(k.total_messages_sent || 0) / Number(k.total_chat_sessions || 1) * 10) / 10 : 0;

    app.innerHTML = `<main class="shell">
      <aside class="sidebar">
        <div class="brand"><div class="logo" aria-hidden="true"></div><div><strong>FocusAI</strong><span>Admin analytics</span></div></div>
        <nav class="nav" aria-label="Dashboard sections">
          <a href="#overview" class="active">Overview</a>
          <a href="#devices">Devices</a>
          <a href="#sessions">Sessions</a>
          <a href="#ips">IPs</a>
          <a href="#errors">Errors</a>
        </nav>
        <div class="side-footer">
          <button id="refresh" class="btn primary" type="button">Refresh</button>
          <button id="export" class="btn" type="button">Export JSON</button>
          <button id="clear" class="btn danger" type="button">Clear activity</button>
          <button id="logout" class="btn" type="button">Logout</button>
        </div>
      </aside>
      <section class="main">
        <header class="topbar" id="overview">
          <div class="title"><span class="eyebrow">🛡️ Private owner dashboard</span><h1>Analytics</h1><p>Only real collected data is shown. Unknown fields stay unknown instead of being guessed.</p></div>
          <div class="status"><span class="pill">Admin: ${esc(me.username || 'admin')}</span><span class="pill">Updated: ${esc(dateFmt(data.generated_at))}</span><span class="pill ${health >= 90 ? 'good' : health >= 70 ? 'warn' : 'bad'}">Health ${fmt(health)}%</span></div>
        </header>

        <section class="grid kpis">
          ${kpiCard('Total visits', k.total_visits, 'Product visits')}
          ${kpiCard('Chat sessions', k.total_chat_sessions, 'Started sessions')}
          ${kpiCard('Messages sent', k.total_messages_sent, 'User prompts')}
          ${kpiCard('AI responses', k.total_ai_responses_generated, 'Generated replies')}
          ${kpiCard('Avg response time', k.average_response_time, 'Latency', 's')}
          ${kpiCard('Active today', k.active_sessions_today, 'Sessions today')}
          ${kpiCard('Created conversations', k.total_conversations_created, 'New chats')}
          ${kpiCard('Deleted conversations', k.total_conversations_deleted, 'Deleted chats')}
          ${kpiCard('Failed calls', k.failed_api_calls, 'Errors')}
          ${kpiCard('Rate limits', k.rate_limit_events, 'Blocked requests')}
        </section>

        <section class="grid three">
          <article class="card"><h2>Response success</h2><strong class="${responseSuccess >= 95 ? 'good' : responseSuccess >= 80 ? 'warn' : ''}" style="font-size:34px;letter-spacing:-.05em">${fmt(responseSuccess)}%</strong><p>AI responses divided by user messages.</p></article>
          <article class="card"><h2>Messages / session</h2><strong style="font-size:34px;letter-spacing:-.05em">${fmt(messagesPerSession)}</strong><p>Useful engagement signal.</p></article>
          <article class="card"><h2>Data source</h2><strong style="font-size:20px">SQLite</strong><p>Stored locally in your analytics database.</p></article>
        </section>

        <section class="grid layout">
          <article class="card"><h2>Daily usage</h2><p>Visits, messages and AI responses for the last 14 days.</p>${drawBars(daily)}</article>
          <article class="card" id="devices"><h2>Device types</h2><p>Desktop / mobile / tablet sessions.</p>${progressList(devices, 'sessions', d => `<div class="row"><div><strong>${deviceIcon('', d.device_type, '')} ${esc(d.device_type || 'Unknown')}</strong><br><span>${fmt(d.messages)} messages</span></div><strong>${fmt(d.sessions)}</strong></div>`)}</article>
        </section>

        <section class="grid layout">
          <article class="card"><h2>Device models / platforms</h2><p>Detected from browser user agent and screen data; exact model is shown only when available.</p>${progressList(profiles, 'sessions', d => `<div class="row"><div><strong>${deviceIcon(d.device_name, '', d.os)} ${esc(d.device_name || 'Unknown device')}</strong><br><span>${esc(d.os || 'Unknown OS')} · ${esc(d.browser || 'Unknown browser')} · last ${esc(since(d.last_seen))}</span></div><strong>${fmt(d.sessions)}</strong></div>`)}</article>
          <article class="card"><h2>Models / providers</h2><p>Most used backend model/provider labels.</p>${progressList(providers, 'count', p => `<div class="row"><div><strong>${esc(p.provider || 'Unknown')}</strong></div><strong>${fmt(p.count)}</strong></div>`)}</article>
        </section>

        <section class="card" id="sessions"><div class="section-head"><div><h2>Recent sessions</h2><p>Session, device, browser, OS, screen and IP.</p></div><input id="sessionSearch" class="search" placeholder="Filter sessions…"></div>${sessionsTable(sessions)}</section>
        <section class="card" id="ips"><h2>IP overview</h2><p>Country flags are based only on trusted proxy/CDN country headers. Local/private IPs are marked as local.</p>${ipTable(ipRows)}</section>
        <section class="card" id="errors"><h2>Recent errors</h2><p>Backend/API/model failures captured by the app.</p>${errorsTable(errors)}</section>
      </section>
    </main>`;

    document.getElementById('refresh').onclick = load;
    document.getElementById('logout').onclick = async () => { await api('/admin/logout', { method: 'POST' }); window.location.href = '/admin/login'; };
    document.getElementById('export').onclick = async () => downloadJson(`focusai-analytics-${new Date().toISOString().slice(0,10)}.json`, await api('/admin/analytics/export'));
    document.getElementById('clear').onclick = async () => { if (confirm('Clear analytics activity? This keeps admin credentials untouched.')) { await api('/admin/analytics/clear', { method: 'POST' }); load(); } };
    const search = document.getElementById('sessionSearch');
    search.oninput = () => filterSessions(search.value);
  }

  function filterSessions(query) {
    if (!lastData) return;
    const card = document.querySelector('#sessions .table-wrap tbody');
    if (!card) return;
    const q = String(query || '').toLowerCase().trim();
    [...card.querySelectorAll('tr')].forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  }

  async function load() {
    try {
      const [me, data] = await Promise.all([api('/admin/me'), api('/admin/analytics/data')]);
      render(me, data);
    } catch (error) {
      if (String(error.message) !== 'unauthorized') {
        app.innerHTML = `<main class="shell"><section class="error">${esc(error.message || error)}</section></main>`;
      }
    }
  }

  load();
  window.setInterval(load, 30000);
})();
