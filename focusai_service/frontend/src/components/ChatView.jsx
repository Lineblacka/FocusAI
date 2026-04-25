import { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble.jsx';
import Composer from './Composer.jsx';

export default function ChatView({
  session,
  input,
  setInput,
  onSubmit,
  onCancel,
  isStreaming,
  onRetry,
  webSearchArmed,
  onToggleWebSearch,
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [session.messages]);

  return (
    <main className="chat-shell">
      <header className="chat-header">
        <div className="chat-title-block">
          <strong>{session.title}</strong>
          <span>{session.messages.length} съобщения</span>
        </div>
      </header>

      <section className="message-list" aria-live="polite">
        {session.messages.map((message) => (
          <MessageBubble key={message.id} message={message} onRetry={onRetry} />
        ))}
        <div ref={bottomRef} />
      </section>

      <div className="sticky-composer">
        <Composer
          value={input}
          onChange={setInput}
          onSubmit={onSubmit}
          onCancel={onCancel}
          isStreaming={isStreaming}
          webSearchArmed={webSearchArmed}
          onToggleWebSearch={onToggleWebSearch}
        />
      </div>
    </main>
  );
}
