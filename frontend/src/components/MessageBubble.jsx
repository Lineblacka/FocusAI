import React from 'react';
import { AlertTriangle } from 'lucide-react';
import MarkdownMessage from './MarkdownMessage.jsx';
import MessageActions from './MessageActions.jsx';
import { MESSAGE_STATUS, ROLE } from '../lib/constants.js';

function TypingDots() {
  return <span className="typing-dots"><span></span><span></span><span></span></span>;
}

function MessageMeta({ isUser }) {
  return <span>{isUser ? 'Ти' : 'FocusAI'}</span>;
}

function MessageSources({ sources }) {
  if (!Array.isArray(sources) || sources.length === 0) return null;

  return (
    <div className="message-sources">
      <strong>Източници</strong>
      <ul className="message-sources-list">
        {sources.map((source, index) => (
          <li key={`${source.url || source.title || 'source'}-${index}`}>
            <a href={source.url} target="_blank" rel="noreferrer">
              {source.title || source.url}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MessageBubble({ message, onRetry }) {
  const isUser = message.role === ROLE.USER;
  const isStreaming = message.status === MESSAGE_STATUS.STREAMING;
  const isError = message.status === MESSAGE_STATUS.ERROR;

  return (
    <article className={`message-row ${isUser ? 'message-row-user' : 'message-row-assistant'}`}>
      <div className="message-meta">
        <MessageMeta isUser={isUser} />
      </div>
      <div className={`message-card ${isUser ? 'message-card-user' : 'message-card-assistant'} ${isError ? 'message-card-error' : ''}`}>
        {!isUser && isStreaming && !message.content ? <TypingDots /> : <MarkdownMessage content={message.content} />}
        {!isUser && isStreaming && message.content ? <span className="stream-cursor" /> : null}
        {!isUser && !isStreaming ? <MessageSources sources={message.sources} /> : null}
        {isError ? <div className="error-line"><AlertTriangle size={15} />{message.error || 'Грешка при генерирането.'}</div> : null}
      </div>
      <MessageActions content={message.content} canRetry={!isUser} onRetry={() => onRetry(message)} />
    </article>
  );
}

export default React.memo(MessageBubble);
