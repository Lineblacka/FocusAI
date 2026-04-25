from typing import Any, Dict

from storage.memory_store import MemoryStore


class CommandService:
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def handle(self, command: str) -> Dict[str, Any]:
        command = command.strip()
        if command == '/help':
            return {'ok': True, 'message': 'Команди: /memory, /add_goal, /add_pattern, /add_commitment'}
        if command == '/memory':
            return {'ok': True, 'message': 'Памет', 'data': self.memory_store.load().get('profile', {})}
        if command.startswith('/add_goal '):
            added = self.memory_store.add_profile_item('goals', command.replace('/add_goal ', '', 1))
            return {'ok': True, 'message': 'Добавено.' if added else 'Вече съществува или е празно.'}
        if command.startswith('/add_pattern '):
            added = self.memory_store.add_profile_item('bad_patterns', command.replace('/add_pattern ', '', 1))
            return {'ok': True, 'message': 'Добавено.' if added else 'Вече съществува или е празно.'}
        if command.startswith('/add_commitment '):
            added = self.memory_store.add_profile_item('commitments', command.replace('/add_commitment ', '', 1))
            return {'ok': True, 'message': 'Добавено.' if added else 'Вече съществува или е празно.'}
        return {'ok': False, 'message': 'Непозната команда.'}
