import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, PanelLeft, X } from 'lucide-react';
import Sidebar from './components/Sidebar.jsx';
import Landing from './components/Landing.jsx';
import ChatView from './components/ChatView.jsx';
import { AdminDashboard, AdminLogin } from './components/Admin.jsx';
import { streamChat, trackAnalyticsEvent } from './api/focusAiClient.js';
import { createId } from './lib/id.js';
import { MAX_SESSIONS, MESSAGE_STATUS, ROLE } from './lib/constants.js';
import {
  createEmptySession,
  deleteStoredSessions,
  loadSessions,
  saveSessions,
  titleForFirstUserMessage,
} from './lib/sessionStore.js';
import { getOrCreateUserId } from './lib/userCookie.js';
import { useBufferedStream } from './hooks/useBufferedStream.js';
import { getDeviceInfo } from './lib/deviceInfo.js';

const MODE_STORAGE_KEY = 'focus_mode';
const MODE_OPTIONS = {
  normal: {
    label: 'Normal',
    description: 'Директен и подкрепящ режим',
  },
  brutal: {
    label: 'Brutal',
    description: 'Без комфорт и без оправдания',
  },
};

function FaqModal({ onClose }) {
  return (
    <div className="faq-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="faq-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="faq-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="faq-header">
          <div>
            <h2 id="faq-title">ЧЗВ</h2>
            <p>Кратко обяснение как работи проектът и какво става с данните ти.</p>
          </div>
          <button type="button" className="faq-close" onClick={onClose} aria-label="Затвори ЧЗВ">
            <X size={18} />
          </button>
        </div>

        <div className="faq-body">
          <div className="faq-section">
            <h3>Какво е FocusAI?</h3>
            <p>
              FocusAI е AI, който те държи мотивиран, помага ти да изградиш дисциплина и не ти позволява лесно
              да се откажеш. Идеята му е да ти дава ясен натиск, структура и следващи стъпки, когато имаш нужда
              от посока, фокус и постоянство.
            </p>
          </div>

          <div className="faq-section">
            <h3>Какво се пази на това устройство?</h3>
            <p>
              Интерфейсът пази чатовете локално в браузъра, за да можеш да ги виждаш отново. Използва се и
              локално cookie ID, за да се разделят сесиите.
            </p>
          </div>

          <div className="faq-section">
            <h3>Следите ли ме?</h3>
            <p>
              В този код няма вградени analytics, рекламни пиксели или логика за продажба на данни към трети
              страни. Все пак не е коректно да се обещава 100% анонимност: сървърът записва базови технически
              логове за заявките, а AI отговорите минават през външен AI доставчик според настройките на проекта.
            </p>
          </div>

          <div className="faq-section">
            <h3>Какво означава това на практика?</h3>
            <p>
              Ако искаш максимална поверителност, не въвеждай чувствителни лични данни, пароли, банкови данни
              или друга секретна информация в чата.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

function IncognitoIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path
        d="M7.1 4.8h9.8c.35 0 .67.2.82.52l1.86 4.04a.9.9 0 0 1-1.64.76l-1.62-3.52H7.69L6.08 10.2a.9.9 0 1 1-1.64-.76L6.3 5.32a.9.9 0 0 1 .8-.52Z"
        fill="currentColor"
      />
      <path
        d="M4.3 10.58c2.53-.53 5.1-.8 7.7-.8 2.6 0 5.17.27 7.7.8a.9.9 0 1 1-.37 1.76c-2.4-.5-4.84-.76-7.33-.76-2.49 0-4.94.25-7.33.76a.9.9 0 0 1-.37-1.76Z"
        fill="currentColor"
      />
      <circle cx="8.15" cy="15.45" r="3.45" stroke="currentColor" strokeWidth="2.2" />
      <circle cx="15.85" cy="15.45" r="3.45" stroke="currentColor" strokeWidth="2.2" />
      <path d="M11.6 15.45h.8" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

function ModeDropdown({ mode, onModeChange }) {
  const menuRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const activeMode = MODE_OPTIONS[mode] || MODE_OPTIONS.normal;

  useEffect(() => {
    function handlePointerDown(event) {
      if (!menuRef.current?.contains(event.target)) {
        setMenuOpen(false);
      }
    }

    window.addEventListener('mousedown', handlePointerDown);
    return () => window.removeEventListener('mousedown', handlePointerDown);
  }, []);

  function selectMode(nextMode) {
    onModeChange(nextMode);
    setMenuOpen(false);
  }

  return (
    <div ref={menuRef} className="mode-dropdown mode-dropdown-topbar">
      <button
        type="button"
        className="mode-dropdown-trigger"
        onClick={() => setMenuOpen((open) => !open)}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        title="Избери режим на FocusAI"
      >
        <span className="mode-dropdown-title">{activeMode.label}</span>
        <ChevronDown size={15} className={`mode-dropdown-chevron ${menuOpen ? 'open' : ''}`} />
      </button>

      {menuOpen ? (
        <div className="mode-dropdown-menu" role="menu">
          {Object.entries(MODE_OPTIONS).map(([key, item]) => (
            <button
              key={key}
              type="button"
              className={`mode-dropdown-item ${mode === key ? 'active' : ''}`}
              onClick={() => selectMode(key)}
              role="menuitemradio"
              aria-checked={mode === key}
            >
              <div className="mode-dropdown-copy">
                <span className="mode-dropdown-item-title">{item.label}</span>
                <span className="mode-dropdown-item-description">{item.description}</span>
              </div>
              {mode === key ? <Check size={15} className="mode-dropdown-check" /> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function loadInitialMode() {
  if (typeof window === 'undefined') return 'normal';
  const stored = window.localStorage.getItem(MODE_STORAGE_KEY);
  return stored === 'brutal' ? 'brutal' : 'normal';
}

export default function App() {
  const pathname = typeof window !== 'undefined' ? window.location.pathname : '/';
  if (pathname === '/admin/login') return <AdminLogin />;
  if (pathname === '/admin/analytics') return <AdminDashboard />;

  const userIdRef = useRef(getOrCreateUserId());
  const initialSessionsRef = useRef(null);
  if (!initialSessionsRef.current) initialSessionsRef.current = loadSessions(userIdRef.current);

  const [sessions, setSessions] = useState(() => initialSessionsRef.current);
  const [activeSessionId, setActiveSessionId] = useState(() => initialSessionsRef.current[0]?.id);
  const [input, setInput] = useState('');
  const [mode, setMode] = useState(loadInitialMode);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [faqOpen, setFaqOpen] = useState(false);
  const [webSearchArmed, setWebSearchArmed] = useState(false);
  const abortRef = useRef(null);
  const assistantIdRef = useRef(null);
  const visitTrackedRef = useRef(false);

  useEffect(() => {
    if (visitTrackedRef.current) return;
    visitTrackedRef.current = true;
    trackAnalyticsEvent('visit', { sessionId: userIdRef.current, device: getDeviceInfo() });
  }, []);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) || sessions[0],
    [sessions, activeSessionId],
  );

  const isStreaming = activeSession?.messages.some((message) => message.status === MESSAGE_STATUS.STREAMING) || false;
  const hasMessages = activeSession?.messages.length > 0;

  useEffect(() => {
    saveSessions(userIdRef.current, sessions);
  }, [sessions]);

  useEffect(() => {
    window.localStorage.setItem(MODE_STORAGE_KEY, mode);
  }, [mode]);

  const updateActiveSession = useCallback((updater) => {
    setSessions((current) => current.map((session) => (
      session.id === activeSessionId ? updater(session) : session
    )));
  }, [activeSessionId]);

  const appendToAssistant = useCallback((chunk) => {
    const messageId = assistantIdRef.current;
    if (!messageId) return;

    updateActiveSession((session) => ({
      ...session,
      updatedAt: new Date().toISOString(),
      messages: session.messages.map((message) => (
        message.id === messageId ? { ...message, content: message.content + chunk } : message
      )),
    }));
  }, [updateActiveSession]);

  const streamBuffer = useBufferedStream(appendToAssistant);

  const finishAssistant = useCallback((status, patch = {}) => {
    streamBuffer.flush();
    const messageId = assistantIdRef.current;
    if (!messageId) return;

    updateActiveSession((session) => ({
      ...session,
      updatedAt: new Date().toISOString(),
      messages: session.messages.map((message) => (
        message.id === messageId ? { ...message, status, ...patch } : message
      )),
    }));

    assistantIdRef.current = null;
    abortRef.current = null;
  }, [streamBuffer, updateActiveSession]);

  const sendMessage = useCallback(async (overrideText, options = {}) => {
    const text = (overrideText ?? input).trim();
    if (!text || isStreaming || !activeSession) return;

    const forceWebSearch = options.forceWebSearch ?? webSearchArmed;
    if (activeSession.messages.length === 0) {
      trackAnalyticsEvent('chat_session', { sessionId: userIdRef.current, device: getDeviceInfo() });
    }
    const webSearch = forceWebSearch ? 'on' : 'auto';

    setInput('');
    setSidebarOpen(false);
    setWebSearchArmed(false);

    const now = new Date().toISOString();
    const userMessage = {
      id: createId('msg'),
      role: ROLE.USER,
      content: text,
      status: MESSAGE_STATUS.DONE,
      createdAt: now,
    };

    const assistantMessage = {
      id: createId('msg'),
      role: ROLE.ASSISTANT,
      content: '',
      status: MESSAGE_STATUS.STREAMING,
      sources: [],
      sourceUserMessage: text,
      createdAt: now,
    };

    assistantIdRef.current = assistantMessage.id;

    updateActiveSession((session) => ({
      ...session,
      title: session.messages.length === 0 ? titleForFirstUserMessage(text) : session.title,
      updatedAt: now,
      messages: [...session.messages, userMessage, assistantMessage],
    }));

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(text, {
        sessionId: `${userIdRef.current}:${activeSession.id}`,
        mode,
        webSearch,
        signal: controller.signal,
        onDelta: (delta) => streamBuffer.push(delta),
        onDone: (data) => finishAssistant(MESSAGE_STATUS.DONE, {
          content: data.reply || '',
          sources: Array.isArray(data.sources) ? data.sources : [],
        }),
        onError: (data) => finishAssistant(MESSAGE_STATUS.ERROR, {
          content: data.reply || '',
          sources: Array.isArray(data.sources) ? data.sources : [],
          error: data.error || 'Грешка в AI услугата.',
        }),
      });
    } catch (error) {
      if (error.name === 'AbortError') {
        finishAssistant(MESSAGE_STATUS.ERROR, { error: 'Генерирането беше спряно.' });
        return;
      }
      finishAssistant(MESSAGE_STATUS.ERROR, { error: error.message || 'Заявката се провали.' });
    }
  }, [activeSession, finishAssistant, input, isStreaming, mode, streamBuffer, updateActiveSession, webSearchArmed]);

  function cancelGeneration() {
    streamBuffer.flush();
    abortRef.current?.abort();
  }

  function createSession() {
    if (sessions.length >= MAX_SESSIONS) {
      setConfirmDialog({
        title: 'Достигнат е лимитът за чатове',
        message: `Можеш да имаш до ${MAX_SESSIONS} запазени чата. Изтрий стар чат или използвай съществуващ, за да продължиш.`,
        confirmLabel: 'Разбрах',
        danger: false,
        onConfirm: () => {},
      });
      return;
    }

    if (isStreaming) cancelGeneration();
    const session = createEmptySession('Нов чат');
    trackAnalyticsEvent('conversation_created', { sessionId: userIdRef.current, device: getDeviceInfo() });
    setSessions((current) => [session, ...current].slice(0, MAX_SESSIONS));
    setActiveSessionId(session.id);
    setInput('');
    setSidebarOpen(false);
    setWebSearchArmed(false);
  }

  function renameSession(id) {
    const current = sessions.find((session) => session.id === id);
    const nextTitle = window.prompt('Преименувай чата:', current?.title || 'Нов чат');
    if (!nextTitle?.trim()) return;

    setSessions((items) => items.map((session) => (
      session.id === id ? { ...session, title: nextTitle.trim(), updatedAt: new Date().toISOString() } : session
    )));
  }

  function confirmDeleteSession(id) {
    const current = sessions.find((session) => session.id === id);
    setConfirmDialog({
      title: 'Изтрий чата?',
      message: `Да изтрия ли „${current?.title || 'Нов чат'}“ от това устройство?`,
      confirmLabel: 'Изтрий',
      danger: true,
      onConfirm: () => {
        trackAnalyticsEvent('conversation_deleted', { sessionId: userIdRef.current, device: getDeviceInfo() });
        const next = sessions.filter((session) => session.id !== id);
        const safe = next.length ? next : [createEmptySession('Нов чат')];
        setSessions(safe);
        if (activeSessionId === id) setActiveSessionId(safe[0].id);
      },
    });
  }

  function confirmDeleteAllSessions() {
    setConfirmDialog({
      title: 'Изтрий всички чатове?',
      message: 'Това ще премахне всички запазени чатове от това устройство. Действието не може да бъде отменено.',
      confirmLabel: 'Изтрий всички',
      danger: true,
      onConfirm: () => {
        trackAnalyticsEvent('conversation_deleted', { sessionId: userIdRef.current, device: getDeviceInfo() });
        const fresh = createEmptySession('Нов чат');
        deleteStoredSessions(userIdRef.current);
        setSessions([fresh]);
        setActiveSessionId(fresh.id);
        setInput('');
        setSidebarOpen(false);
        setWebSearchArmed(false);
      },
    });
  }

  function closeConfirmDialog() {
    setConfirmDialog(null);
  }

  function runConfirmDialog() {
    const action = confirmDialog?.onConfirm;
    closeConfirmDialog();
    action?.();
  }

  function retryMessage(message) {
    if (!message.sourceUserMessage || isStreaming) return;
    updateActiveSession((session) => ({
      ...session,
      messages: session.messages.filter((item) => item.id !== message.id),
    }));
    sendMessage(message.sourceUserMessage);
  }

  return (
    <div className="app-frame">
      <div className={`app-shell ${sidebarOpen ? 'sidebar-expanded' : 'sidebar-collapsed'}`}>
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onNew={createSession}
          onSelect={(id) => {
            setActiveSessionId(id);
            setSidebarOpen(false);
          }}
          onRename={renameSession}
          onDelete={confirmDeleteSession}
          onDeleteAll={confirmDeleteAllSessions}
          onOpenFaq={() => setFaqOpen(true)}
          sidebarOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <section className="workspace-shell">
          <header className="topbar">
            <div className="topbar-left">
              <button
                type="button"
                className="ghost-toggle"
                onClick={() => setSidebarOpen((open) => !open)}
                aria-label={sidebarOpen ? 'Скрий страничното меню' : 'Покажи страничното меню'}
              >
                <PanelLeft size={18} />
              </button>
              <ModeDropdown mode={mode} onModeChange={setMode} />
            </div>

            <div className="topbar-badges">
              <div className="status-pill active-pill icon-pill" title="Поверителен режим" aria-label="Поверителен режим">
                <IncognitoIcon />
              </div>
            </div>
          </header>

          {hasMessages ? (
            <ChatView
              session={activeSession}
              input={input}
              setInput={setInput}
              onSubmit={() => sendMessage()}
              onCancel={cancelGeneration}
              isStreaming={isStreaming}
              onRetry={retryMessage}
              webSearchArmed={webSearchArmed}
              onToggleWebSearch={() => setWebSearchArmed((current) => !current)}
            />
          ) : (
            <Landing
              input={input}
              setInput={setInput}
              onSubmit={() => sendMessage()}
              disabled={isStreaming}
              onExampleClick={(text) => sendMessage(text)}
              webSearchArmed={webSearchArmed}
              onToggleWebSearch={() => setWebSearchArmed((current) => !current)}
            />
          )}
        </section>
      </div>

      {sidebarOpen ? (
        <button type="button" className="app-overlay" aria-label="Затвори страничното меню" onClick={() => setSidebarOpen(false)} />
      ) : null}

      {confirmDialog ? (
        <div className="confirm-backdrop" role="presentation" onMouseDown={closeConfirmDialog}>
          <section
            className="confirm-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h2 id="confirm-title">{confirmDialog.title}</h2>
            <p>{confirmDialog.message}</p>
            <div className="confirm-actions">
              <button type="button" className="confirm-button secondary" onClick={closeConfirmDialog}>Отказ</button>
              <button
                type="button"
                className={`confirm-button ${confirmDialog.danger ? 'danger' : 'primary'}`}
                onClick={runConfirmDialog}
                autoFocus
              >
                {confirmDialog.confirmLabel || 'Потвърди'}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {faqOpen ? <FaqModal onClose={() => setFaqOpen(false)} /> : null}
    </div>
  );
}
