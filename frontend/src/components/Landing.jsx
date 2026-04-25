import { useMemo } from 'react';
import Composer from './Composer.jsx';

const SUGGESTION_POOL = [
  'Създай 7-дневен план за фокус',
  'Разгледай бизнес идея',
  'Помогни ми да започна отначало',
  'Направи ми сутрешен режим за повече енергия',
  'Подреди ми задачите за днешния ден',
  'Дай ми кратък план за учене без разсейване',
  'Помогни ми да спра отлагането',
  'Измисли ми проста стратегия за нов проект',
  'Разбий голяма цел на малки стъпки',
  'Помогни ми да си върна концентрацията',
];

function shuffle(list) {
  const items = [...list];
  for (let index = items.length - 1; index > 0; index -= 1) {
    const nextIndex = Math.floor(Math.random() * (index + 1));
    [items[index], items[nextIndex]] = [items[nextIndex], items[index]];
  }
  return items;
}

export default function Landing({
  input,
  setInput,
  onSubmit,
  disabled,
  onExampleClick,
  webSearchArmed,
  onToggleWebSearch,
}) {
  const suggestions = useMemo(() => shuffle(SUGGESTION_POOL).slice(0, 3), []);

  return (
    <main className="landing">
      <section className="landing-card" aria-label="Начален екран на FocusAI">
        <h1>FocusAI</h1>
        <Composer
          value={input}
          onChange={setInput}
          onSubmit={onSubmit}
          disabled={disabled}
          compact
          webSearchArmed={webSearchArmed}
          onToggleWebSearch={onToggleWebSearch}
        />
        <div className="suggestion-strip">
          {suggestions.map((item) => (
            <button key={item} type="button" className="suggestion-chip" onClick={() => onExampleClick(item)}>
              {item}
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
