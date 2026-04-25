import re
from typing import Any, Dict


class QualityService:
    banned_words = ['идиот', 'тъп', 'слабак', 'жалък', 'мързеливец']
    forbidden_prefixes = [
        'Respond short.',
        'Respond shortly.',
        'Answer briefly.',
        'Answer short.',
        'Отговори кратко.',
        'Кратък отговор:',
        'Режим:',
        'Нормален режим:',
        'Строг режим:',
        'We must answer identity:',
        'We need to answer:',
        '**Строг режим**',
        'Разпознат режим:',
    ]
    forbidden_fragments = [
        'We responded.',
        'Като AI модел от OpenAI',
        'базиран на GPT',
        'работя върху архитектурата GPT',
        'от OpenAI',
    ]
    informal_replacements = {
        'Вие': 'ти',
        'Ви': 'ти',
        'Вас': 'теб',
        'Вашият': 'твоят',
        'Вашата': 'твоята',
        'Вашето': 'твоето',
        'Ваши': 'твои',
        'Ваш': 'твой',
        'бихте': 'би',
        'желаете': 'искаш',
    }

    def clean_output(self, text: str) -> str:
        cleaned = text.strip()
        changed = True
        while changed:
            changed = False
            for prefix in self.forbidden_prefixes:
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix):].strip()
                    changed = True

        for fragment in self.forbidden_fragments:
            cleaned = cleaned.replace(fragment, '').strip()

        # Preserve markdown structure: normalize spaces/tabs per line, not newlines.
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
        cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = '\n'.join(re.sub(r'[ \t]{2,}', ' ', line).strip() for line in cleaned.split('\n')).strip()

        for old, new in self.informal_replacements.items():
            cleaned = cleaned.replace(old, new)

        return cleaned

    def contains_banned_word(self, text: str) -> bool:
        for word in self.banned_words:
            pattern = rf'\b{re.escape(word)}\b'
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        return False

    def is_empty_or_weak(self, reply: str) -> bool:
        return not reply or len(reply.strip()) < 20

    def is_history_message_usable(self, role: str, content: str) -> bool:
        text = (content or '').strip()
        if not text:
            return False
        if role != 'assistant':
            return True

        lowered = text.lower()
        forbidden_markers = [
            'we responded.',
            'openai',
            'gpt-4',
            'gpt4',
            'архитектурата gpt',
            'като ai модел',
        ]
        return not any(marker in lowered for marker in forbidden_markers)

    def check(self, reply: str) -> Dict[str, Any]:
        text = reply.strip().lower()
        issues = []
        if self.contains_banned_word(reply):
            issues.append('possible_insult')
        if len(reply.strip()) < 20:
            issues.append('too_short')
        if len(reply.split()) > 350:
            issues.append('too_long')

        action_markers = ['?', 'започни', 'избери', 'напиши', 'провери', 'действай', 'реши', 'направи', 'първият ход', 'как ще', 'кое ти пречи']
        if not any(marker in text for marker in action_markers):
            issues.append('missing_action_push')

        return {'passed': len(issues) == 0, 'issues': issues}
