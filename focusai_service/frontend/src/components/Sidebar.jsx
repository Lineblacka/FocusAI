import { CircleHelp, Edit3, Github, MessageSquarePlus, Trash2, X, XCircle } from 'lucide-react';

export default function Sidebar({
  sessions,
  activeSessionId,
  onNew,
  onSelect,
  onRename,
  onDelete,
  onDeleteAll,
  onOpenFaq,
  sidebarOpen,
  onClose,
}) {
  return (
    <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-brand" aria-label="Лого на FocusAI" role="img" />
        <button type="button" className="sidebar-close" onClick={onClose} aria-label="Затвори">
          <X size={18} />
        </button>
      </div>

      <button type="button" className="new-chat" onClick={onNew}>
        <MessageSquarePlus size={16} />
        <span>Нов чат</span>
      </button>

      <div className="sidebar-section-label">История</div>

      <div className="session-list">
        {sessions.map((session) => (
          <div key={session.id} className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}>
            <button type="button" className="session-title" onClick={() => onSelect(session.id)}>
              <span>{session.title}</span>
              <small>{session.messages.length ? `${session.messages.length} съобщения` : 'Празен чат'}</small>
            </button>
            <button type="button" className="session-action" onClick={() => onRename(session.id)} aria-label="Преименувай">
              <Edit3 size={14} />
            </button>
            <button type="button" className="session-action danger" onClick={() => onDelete(session.id)} aria-label="Изтрий">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-footer-actions">
        <button type="button" className="delete-all" onClick={onDeleteAll}>
          <XCircle size={15} />
          <span>Изтрий всички чатове</span>
        </button>

        <button type="button" className="delete-all" onClick={onOpenFaq}>
          <CircleHelp size={15} />
          <span>ЧЗВ</span>
        </button>

        <a
          className="github-button"
          href="https://github.com/Lineblacka"
          target="_blank"
          rel="noreferrer"
          aria-label="GitHub на Lineblacka"
          title="GitHub на Lineblacka"
        >
          <Github size={17} />
        </a>
      </div>
    </aside>
  );
}
