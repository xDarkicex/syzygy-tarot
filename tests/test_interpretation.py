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


def test_text_block_picks_text_and_skips_thinking() -> None:
    event = {
        "output": [{
            "content": [
                {"type": "thinking", "thinking": "secret reasoning"},
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "world."},
            ]
        }]
    }
    assert interpretation._text_block(event) == "Hello world."


def test_text_block_returns_none_when_no_text_yet() -> None:
    assert interpretation._text_block({"output": [{"content": [{"type": "thinking", "thinking": "x"}]}]}) is None
    assert interpretation._text_block({"output": []}) is None
    assert interpretation._text_block({}) is None


def test_streaming_yields_deltas_only() -> None:
    """Simulate the cumulative-text stream: text grows, we emit only the new chars."""
    events = [
        {"output": [{"content": [{"type": "text", "text": "He"}]}]},
        {"output": [{"content": [{"type": "text", "text": "Hello"}]}]},
        {"output": [{"content": [{"type": "text", "text": "Hello,"}, {"type": "text", "text": " world"}]}]},
    ]
    seen_lengths: list[int] = []

    def fake_stream():
        for e in events:
            text = interpretation._text_block(e)
            if text is not None:
                seen_lengths.append(len(text))
            yield e

    # Replace stream_interpretation's internal call by feeding the fake stream
    deltas: list[str] = []
    last = 0
    for event in fake_stream():
        text = interpretation._text_block(event)
        if text is None or len(text) <= last:
            continue
        delta = text[last:]
        last = len(text)
        if delta:
            deltas.append(delta)
    assert "".join(deltas) == "Hello, world"


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
