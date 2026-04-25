from services.quality_service import QualityService


def test_clean_output_preserves_markdown_newlines():
    service = QualityService()

    content = 'Ред 1\n\n| A | B |\n| - | - |\n| 1 | 2 |\n\nРед 2'
    cleaned = service.clean_output(content)

    assert '| A | B |' in cleaned
    assert '\n| - | - |\n' in cleaned
    assert 'Ред 1\n\n| A | B |' in cleaned


def test_history_message_filter_blocks_tainted_identity_text():
    service = QualityService()

    assert service.is_history_message_usable('assistant', 'We responded. Като AI модел от OpenAI') is False
    assert service.is_history_message_usable('assistant', 'Нормален чист отговор') is True
