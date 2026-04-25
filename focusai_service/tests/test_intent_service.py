from services.intent_service import IntentService


def test_identity_intent():
    assert IntentService().classify('Кой си ти') == 'identity_question'


def test_business_intent():
    assert IntentService().classify('Искам да направя онлайн магазин') == 'idea_review'
