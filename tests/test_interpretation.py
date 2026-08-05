"""Tests for the interpretation builder and streaming shape.

The LLM itself is not called in unit tests; we test:
- the prompt builder
- the cumulative-text extraction
- the streaming delta computation
- the missing-API-key path
"""

from __future__ import annotations

from datetime import date

import pytest

from app.data.loader import load_deck
from app.domain.reading import build_reading
from app.domain.seeding import DailySeed, Querent
from app.domain.spreads import SIGNATURE, SINGLE
from app.services import interpretation


def _reading(rank: int = 3):
    deck = load_deck()
    spread = SIGNATURE if rank > 1 else SINGLE
    return build_reading(
        deck,
        spread,
        Querent(name="Ada", age=29, resonance="Female"),
        DailySeed(),
        date(2026, 8, 5),
    )


def test_prompt_names_querent_and_lists_every_card() -> None:
    reading = _reading(3)
    prompt = interpretation.build_prompt(reading)
    assert "Ada" in prompt
    assert "age 29" in prompt
    for d in reading.drawn:
        assert d.card.name in prompt
        assert d.position.title in prompt
        assert "reversed" if d.is_reversed else "upright" in prompt


def test_stream_emits_deltas_from_cumulative_events() -> None:
    """The Merge gateway emits events where each event's output[0].content[]
    contains the cumulative text so far. We track the previous total length
    and emit only the new characters as deltas (a generator, not a list, so
    each delta is yielded as it arrives and the browser gets a real stream).
    """
    events = [
        {"output": [{"content": [{"type": "text", "text": "Gentry"}]}]},
        {"output": [{"content": [{"type": "text", "text": "Gentry,"}]}]},
        {"output": [{"content": [{"type": "text", "text": "Gentry, the"}]}]},
        {"output": [{"content": [{"type": "text", "text": "Gentry, the shape"}]}]},
    ]

    class FakeStream:
        def __init__(self):
            self._events = iter(events)
        def __iter__(self):
            return self._events

    from app.services import interpretation as mod
    original = mod._client

    def client():
        return type("S", (), {"responses": type(
            "R", (), {"create": staticmethod(lambda **kw: FakeStream())}
        )()})()

    mod._client = client
    try:
        deltas = list(mod.stream_interpretation(_reading(3)))
    finally:
        mod._client = original

    assert deltas == ["Gentry", ",", " the", " shape"], (
        f"each event should produce a delta equal to the new chars, got {deltas}"
    )


def test_stream_skips_thinking_blocks() -> None:
    """Thinking blocks should be ignored; only the text block is read."""
    events = [
        {"output": [{"content": [
            {"type": "thinking", "thinking": "secret reasoning"},
            {"type": "text", "text": "Hello"},
        ]}]},
        {"output": [{"content": [
            {"type": "thinking", "thinking": "more secret"},
            {"type": "text", "text": "Hello world"},
        ]}]},
    ]

    class FakeStream:
        def __init__(self):
            self._events = iter(events)
        def __iter__(self):
            return self._events

    from app.services import interpretation as mod
    original = mod._client

    def client():
        return type("S", (), {"responses": type(
            "R", (), {"create": staticmethod(lambda **kw: FakeStream())}
        )()})()

    mod._client = client
    try:
        deltas = list(mod.stream_interpretation(_reading(3)))
    finally:
        mod._client = original

    assert deltas == ["Hello", " world"], deltas


def test_generate_interpretation_without_api_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("SYZYGY_MERGE_API_KEY", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="SYZYGY_MERGE_API_KEY"):
            interpretation.generate_interpretation(_reading())
    finally:
        get_settings.cache_clear()


def test_extract_text_skips_thinking_blocks() -> None:
    """_extract_text walks the OutputMessage.content list and collects text from
    TextContent blocks, skipping ThinkingContent. Works for both dict and
    Pydantic shapes.
    """
    class FakeBlock:
        def __init__(self, type_: str, text: str):
            self.type = type_
            self.text = text

    class FakeMessage:
        def __init__(self, blocks):
            self.content = blocks

    class FakeResponse:
        def __init__(self, messages):
            self.output = messages

    response = FakeResponse([
        FakeMessage([
            FakeBlock("thinking", "secret reasoning"),
            FakeBlock("text", "Hello world"),
        ])
    ])
    assert interpretation._extract_text(response) == "Hello world"

    # And the dict shape, which is what the streaming path delivers.
    dict_response = {
        "output": [
            {"content": [
                {"type": "thinking", "thinking": "secret"},
                {"type": "text", "text": "Streamed."},
            ]}
        ]
    }
    assert interpretation._extract_text(dict_response) == "Streamed."
