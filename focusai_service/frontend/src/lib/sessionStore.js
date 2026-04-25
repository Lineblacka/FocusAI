import { createId } from './id.js';
import { ROLE, MESSAGE_STATUS, STORAGE_PREFIX, MAX_SESSIONS } from './constants.js';

export function storageKeyForUser(userId) {
  return `${STORAGE_PREFIX}.${userId}`;
}

function sessionTitleFromText(text) {
  const normalized = text.replace(/\s+/g, ' ').trim();
  if (!normalized) return 'Нов чат';
  return normalized.length > 38 ? `${normalized.slice(0, 38)}...` : normalized;
}

export function createEmptySession(title = 'Нов чат') {
  const now = new Date().toISOString();
  return {
    id: createId('session'),
    title,
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

export function normalizeSessions(value) {
  if (!Array.isArray(value) || value.length === 0) return [createEmptySession()];

  const normalized = value.map((session) => ({
    id: session.id || createId('session'),
    title: session.title || 'Нов чат',
    messages: Array.isArray(session.messages)
      ? session.messages.map((message) => ({
        id: message.id || createId('msg'),
        role: message.role === ROLE.USER ? ROLE.USER : ROLE.ASSISTANT,
        content: message.content || '',
        status: message.status || MESSAGE_STATUS.DONE,
        error: message.error || null,
        model: message.model || null,
        latencySeconds: message.latencySeconds || null,
        sources: Array.isArray(message.sources) ? message.sources : [],
        sourceUserMessage: message.sourceUserMessage || null,
        createdAt: message.createdAt || new Date().toISOString(),
      }))
      : [],
    createdAt: session.createdAt || new Date().toISOString(),
    updatedAt: session.updatedAt || new Date().toISOString(),
  }));

  return normalized.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt)).slice(0, MAX_SESSIONS);
}

export function loadSessions(userId) {
  try {
    return normalizeSessions(JSON.parse(localStorage.getItem(storageKeyForUser(userId))));
  } catch {
    return [createEmptySession()];
  }
}

export function saveSessions(userId, sessions) {
  localStorage.setItem(storageKeyForUser(userId), JSON.stringify(normalizeSessions(sessions)));
}

export function deleteStoredSessions(userId) {
  localStorage.removeItem(storageKeyForUser(userId));
}

export function titleForFirstUserMessage(text) {
  return sessionTitleFromText(text);
}
