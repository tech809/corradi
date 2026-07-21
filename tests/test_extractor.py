from app.llm.extractor import _strip_fences


def test_strip_fences_json_block():
    assert _strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_fences_plain():
    assert _strip_fences('{"a": 1}') == '{"a": 1}'


def test_strip_fences_bare_fence():
    assert _strip_fences('```\n{"a": 1}\n```') == '{"a": 1}'
