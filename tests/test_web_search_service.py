from services.web_search_service import WebSearchService


def test_should_search_respects_preference():
    service = WebSearchService()

    assert service.should_search('Какво е времето днес?', 'auto') is True
    assert service.should_search('Направи ми план за деня', 'auto') is False
    assert service.should_search('Направи ми план за деня', 'on') is True
    assert service.should_search('Какво е времето днес?', 'off') is False


def test_build_context_returns_none_when_search_not_needed():
    service = WebSearchService()
    context, meta = service.build_context('Направи ми план за деня', 'off')

    assert context is None
    assert meta['used'] is False
