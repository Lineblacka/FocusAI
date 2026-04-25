INTENT_RULES = {
    'identity_question': ['кой си', 'какво си', 'за какво си', 'какво правиш', 'ти кой си'],
    'time_question': ['коя година сме', 'коя дата сме', 'колко е часът', 'колко е часа', 'днес коя дата е', 'коя година е'],
    'small_talk': ['здравей', 'здрасти', 'как си', 'hello', 'hi', 'hey'],
    'excuse': ['нямам време', 'нямам мотивация', 'утре', 'изморен съм', 'не мога', 'трудно е', 'няма смисъл'],
    'failure_report': ['провалих', 'пропуснах', 'пак не', 'не успях', 'счупих режима', 'изоставам'],
    'goal_planning': ['искам да започна', 'план', 'цел', 'как да', 'програма', 'режим'],
    'idea_review': ['идея', 'мисля да', 'искам да направя', 'искам да си направя', 'проект', 'продукт', 'бизнес', 'магазин', 'бранд', 'онлайн магазин'],
    'progress_report': ['направих', 'успях', 'готово', 'днес изпълних', 'отчет'],
    'emotional_support': ['зле съм', 'не издържам', 'тревожно', 'депресиран', 'паника', 'сам съм'],
}


class IntentService:
    def classify(self, user_input: str) -> str:
        text = user_input.lower().strip()
        for intent, keywords in INTENT_RULES.items():
            if any(keyword in text for keyword in keywords):
                return intent
        return 'general_question'
