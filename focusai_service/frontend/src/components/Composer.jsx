import { Globe, Plus, Send, Square } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

export default function Composer({
  value,
  onChange,
  onSubmit,
  onCancel,
  disabled,
  isStreaming,
  compact = false,
  webSearchArmed = false,
  onToggleWebSearch,
}) {
  const ref = useRef(null);
  const menuRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);

  useEffect(() => {
    function handlePointerDown(event) {
      if (!menuRef.current?.contains(event.target)) {
        setMenuOpen(false);
      }
    }

    window.addEventListener('mousedown', handlePointerDown);
    return () => window.removeEventListener('mousedown', handlePointerDown);
  }, []);

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  function handleWebSearchToggle() {
    onToggleWebSearch?.();
    setMenuOpen(false);
  }

  return (
    <div className="composer-stack">
      <div className={`composer ${compact ? 'composer-compact' : ''}`}>
        <div ref={menuRef} className="composer-menu">
          <button
            type="button"
            className={`composer-side-button ${webSearchArmed ? 'composer-side-button-active' : ''}`}
            aria-label="Още опции"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <Plus size={16} />
          </button>

          {menuOpen ? (
            <div className="composer-dropdown" role="menu">
              <button
                type="button"
                className={`composer-dropdown-item ${webSearchArmed ? 'active' : ''}`}
                onClick={handleWebSearchToggle}
                role="menuitemcheckbox"
                aria-checked={webSearchArmed}
              >
                <Globe size={15} />
                <div className="composer-dropdown-copy">
                  <span>Web search</span>
                  <small>Търси в интернет за следващото съобщение</small>
                </div>
              </button>
            </div>
          ) : null}
        </div>

        <div className="composer-input-wrap">
          <textarea
            ref={ref}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Кажи ми целта си. Ще те накарам да я изпълниш."
            rows={1}
            disabled={disabled}
          />
        </div>

        {isStreaming ? (
          <button type="button" className="send-button stop-button" onClick={onCancel} aria-label="Спри">
            <Square size={18} fill="currentColor" />
          </button>
        ) : (
          <button type="button" className="send-button" onClick={onSubmit} disabled={!value.trim() || disabled} aria-label="Изпрати">
            <Send size={17} />
          </button>
        )}
      </div>

      {webSearchArmed ? (
        <div className="composer-search-hint">
          <Globe size={13} />
          <span>Web search е включен за следващото съобщение.</span>
        </div>
      ) : null}
    </div>
  );
}
