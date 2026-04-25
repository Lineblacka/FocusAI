import { Check, Copy, RotateCcw } from 'lucide-react';
import { useState } from 'react';

export default function MessageActions({ content, canRetry, onRetry }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(content || '');
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="message-actions">
      <button type="button" className="icon-button" onClick={copy} aria-label="Копирай">
        {copied ? <Check size={16} /> : <Copy size={16} />}
      </button>
      {canRetry ? (
        <button type="button" className="icon-button" onClick={onRetry} aria-label="Опитай отново">
          <RotateCcw size={16} />
        </button>
      ) : null}
    </div>
  );
}
