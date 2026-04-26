const API_BASE = import.meta.env.VITE_FOCUSAI_API_URL || '';

function toUrl(path) {
  return `${API_BASE}${path}`;
}

async function parseError(response) {
  try {
    const data = await response.json();
    return data?.detail?.message || data?.detail?.error || data?.message || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export async function chat(message, { sessionId = 'default', mode = 'normal', webSearch = 'auto', signal } = {}) {
  const response = await fetch(toUrl('/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, mode, web_search: webSearch }),
    signal,
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

function parseSseEvents(buffer) {
  const events = [];
  const blocks = buffer.split(/\n\n/);
  const rest = blocks.pop() || '';

  for (const block of blocks) {
    let event = 'message';
    const dataLines = [];

    for (const line of block.split(/\n/)) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
    }

    if (!dataLines.length) continue;

    try {
      events.push({ event, data: JSON.parse(dataLines.join('\n')) });
    } catch {
      events.push({ event, data: { raw: dataLines.join('\n') } });
    }
  }

  return { events, rest };
}

export async function streamChat(message, handlers = {}) {
  const {
    sessionId = 'default',
    mode = 'normal',
    webSearch = 'auto',
    signal,
    onStart,
    onDelta,
    onDone,
    onError,
  } = handlers;

  const response = await fetch(toUrl('/chat/stream'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, mode, web_search: webSearch }),
    signal,
  });

  if (!response.ok) throw new Error(await parseError(response));
  if (!response.body) throw new Error('Липсва streaming отговор от API.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseEvents(buffer);
    buffer = parsed.rest;

    for (const item of parsed.events) {
      if (item.event === 'start') onStart?.(item.data);
      if (item.event === 'delta') onDelta?.(item.data.delta || '', item.data);
      if (item.event === 'done') {
        onDone?.(item.data);
        return;
      }
      if (item.event === 'error') {
        onError?.(item.data);
        return;
      }
    }
  }
}


export async function adminLogin(username, password) {
  const response = await fetch(toUrl('/admin/login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function adminLogout() {
  const response = await fetch(toUrl('/admin/logout'), {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function getAdminMe() {
  const response = await fetch(toUrl('/admin/me'), {
    method: 'GET',
    credentials: 'include',
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function getAdminAnalytics() {
  const response = await fetch(toUrl('/admin/analytics/data'), {
    method: 'GET',
    credentials: 'include',
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}


export async function exportAdminAnalytics() {
  const response = await fetch(toUrl('/admin/analytics/export'), {
    method: 'GET',
    credentials: 'include',
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function clearAdminAnalytics() {
  const response = await fetch(toUrl('/admin/analytics/clear'), {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function trackAnalyticsEvent(event, { sessionId = '', device = {} } = {}) {
  try {
    await fetch(toUrl('/analytics/event'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      keepalive: true,
      body: JSON.stringify({ event, session_id: sessionId, device }),
    });
  } catch {
    // Analytics must never block the product UI.
  }
}
