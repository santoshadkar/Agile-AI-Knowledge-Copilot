from unittest.mock import MagicMock

import pytest

from app.graph.llm import invoke_with_fallback


def _fake_model(name: str, *, content=None, error=None):
    # spec=[] so MagicMock doesn't auto-generate a truthy `.model_name`
    # attribute on access -- _model_label checks model_name before model
    # (matching ChatOpenAI's real attribute name), and an unset MagicMock
    # attribute is truthy, not None, which silently broke this the first
    # time the label-lookup order changed.
    model = MagicMock(spec=["invoke", "model", "model_name"])
    model.model = name
    model.model_name = name
    if error is not None:
        model.invoke.side_effect = error
    else:
        model.invoke.return_value = MagicMock(content=content)
    return model


def test_primary_success_never_touches_fallbacks():
    primary = _fake_model("primary", content="answer")
    fallback = _fake_model("fallback", content="should not be used")

    result = invoke_with_fallback(["msg"], primary, fallback)

    assert result == "answer"
    fallback.invoke.assert_not_called()


def test_falls_through_to_second_model_on_first_failure():
    primary = _fake_model("primary", error=RuntimeError("503"))
    fallback = _fake_model("fallback", content="fallback answer")

    result = invoke_with_fallback(["msg"], primary, fallback)

    assert result == "fallback answer"
    primary.invoke.assert_called_once()
    fallback.invoke.assert_called_once()


def test_three_tier_chain_falls_through_to_third_model():
    """Mirrors the real chain: qwen -> liquid -> nvidia, all via OpenRouter."""
    primary = _fake_model("qwen/qwen3.8-27b:free", error=RuntimeError("429 rate-limited"))
    secondary = _fake_model("liquid/lfm-2.5-2.6b:free", error=RuntimeError("503 provider overloaded"))
    tertiary = _fake_model("nvidia/nemotron-3-super-120b-a12b:free", content="third-tier answer")

    result = invoke_with_fallback(["msg"], primary, secondary, tertiary)

    assert result == "third-tier answer"
    for model in (primary, secondary, tertiary):
        model.invoke.assert_called_once()


def test_all_models_failing_raises_with_every_reason():
    primary = _fake_model("a", error=RuntimeError("503"))
    secondary = _fake_model("b", error=RuntimeError("504"))
    tertiary = _fake_model("c", error=RuntimeError("connection reset"))

    with pytest.raises(RuntimeError) as exc_info:
        invoke_with_fallback(["msg"], primary, secondary, tertiary)

    message = str(exc_info.value)
    assert "a" in message and "503" in message
    assert "b" in message and "504" in message
    assert "c" in message and "connection reset" in message


def test_no_models_raises_value_error():
    with pytest.raises(ValueError):
        invoke_with_fallback(["msg"])


# --- extract_text ------------------------------------------------------------


def test_extract_text_plain_string():
    from app.graph.llm import extract_text

    assert extract_text(MagicMock(content="hello")) == "hello"


def test_extract_text_content_parts_list():
    """Gemini's .content is sometimes a list of content-part dicts rather
    than a plain string (observed live, not hypothetical)."""
    from app.graph.llm import extract_text

    message = MagicMock(content=[{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}])
    assert extract_text(message) == "hello world"
