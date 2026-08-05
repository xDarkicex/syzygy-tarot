"""LLM-powered combined reading interpretation via Merge Gateway / deepseek-v4-flash.

The system reads a reading (querent + spread + drawn cards with orientations and
meanings) and asks the model to synthesise a single coherent reading that ties the
cards together in light of what each position asks.
"""

from __future__ import annotations

import os
from typing import Iterable

from merge_gateway import MergeGateway

from app.config import get_settings
from app.domain.reading import Reading

SYSTEM_PROMPT = """\
You are a thoughtful tarot reader. You write in second person, address the person
directly, and keep your voice grounded — never mystical jargon, never fortune-
cookie generalities. You read for the specific cards and the specific spread in
front of you, not for a generic situation.

You respect the card orientations: an upright card reads in its main meaning, a
reversed card reads in its shadow. When a card is reversed, name that fact in your
interpretation and let the reversal shape what the card is saying.

You write short paragraphs. No bullet points, no numbered lists, no headings.
Two to four paragraphs total. Aim for 180 to 320 words.

Open with the querent's first name. Then write one opening sentence that names
the overall tone. Then walk the spread's positions in order — for each
position, read its card as an answer to that position's specific question.
Close with one short paragraph on what to carry away.
"""


def _card_line(card, drawn) -> str:
    orientation = "reversed" if drawn.is_reversed else "upright"
    body = " ".join(drawn.body).strip()
    summary = drawn.summary
    return (
        f"- {drawn.position.title} — {card.name} ({orientation}): "
        f"{summary} {body}"
    )


def build_prompt(reading: Reading) -> str:
    """Compose the user message that asks for a combined interpretation."""
    spread_name = reading.spread.name
    card_lines = "\n".join(_card_line(d.card, d) for d in reading.drawn)
    name_part = (
        f' The querent is {reading.querent.name}, age {reading.querent.age}.'
        if reading.querent.name.strip() else ""
    )
    return (
        f"Read the following {spread_name.lower()}.{name_part}\n\n"
        f"{card_lines}\n\n"
        "Write the combined meaning: a short opening that names the overall tone, "
        "then a paragraph that walks through the positions in order and shows how "
        "they speak to each other, then a closing paragraph on what to carry away. "
        "Keep it to two to four short paragraphs, grounded in the specific cards."
    )


def _client() -> MergeGateway:
    settings = get_settings()
    api_key = os.getenv("SYZYGY_MERGE_API_KEY") or settings.merge_api_key
    if not api_key:
        raise RuntimeError("SYZYGY_MERGE_API_KEY is not set")
    return MergeGateway(api_key=api_key, base_url=settings.merge_base_url)


def _messages(reading: Reading) -> list[dict]:
    return [
        {"type": "message", "role": "system", "content": SYSTEM_PROMPT},
        {"type": "message", "role": "user", "content": build_prompt(reading)},
    ]


def generate_interpretation(reading: Reading) -> str:
    """Synchronous full interpretation. Use this when you just want the final text.

    Concatenates every cumulative text chunk from the streaming path. The stream
    is used (not the non-streaming path) because it surfaces both Thinking and
    Text content blocks, and the same walker works for the share page refresh.
    """
    chunks: list[str] = []
    for chunk in stream_interpretation(reading):
        chunks.append(chunk)
    return "".join(chunks).strip()


def stream_interpretation(reading: Reading) -> Iterable[str]:
    """Yield text deltas as the LLM streams.

    The Merge gateway emits events where each event carries the cumulative text
    so far inside ``output[0].content[].text`` (alongside any thinking blocks
    the model produced). We track the last-seen length and yield only the
    characters that were added in the latest event. Each delta is yielded
    immediately so the SSE consumer can flush it to the browser for a
    typewriter effect.
    """
    stream = _client().responses.create(
        model="deepseek-v4-flash",
        input=_messages(reading),
        max_tokens=900,
        stream=True,
    )
    last_text_len = 0
    try:
        for event in stream:
            text = _text_block(event)
            if text is None or len(text) <= last_text_len:
                continue
            delta = text[last_text_len:]
            last_text_len = len(text)
            if delta:
                yield delta
    finally:
        if hasattr(stream, "close"):
            stream.close()


def _text_block(event: object) -> str | None:
    """Pull the cumulative text from an event's output, ignoring thinking blocks.

    Each streaming event has the cumulative text inside output[0].content[],
    and there is one block per content type (thinking or text). The text block
    grows across events; the thinking block also grows but we skip it.
    """
    output = _get_attr(event, "output")
    if not isinstance(output, list) or not output:
        return None
    first = output[0]
    if not isinstance(first, dict):
        # The merge-gateway-python SDK parses each event into a Pydantic model.
        content = getattr(first, "content", None)
    else:
        content = first.get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for item in content:
        text = _text_field(item)
        if text is not None:
            parts.append(text)
    return "".join(parts) if parts else None


def _get_attr(obj: object, key: str) -> object | None:
    """Read a key from either a dict or a Pydantic-style object.

    The merge-gateway-python package parses SSE events into Pydantic models,
    so we need to support attribute access. Some fallbacks (the non-streaming
    path) return dicts, so we accept those too.
    """
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _text_field(item: object) -> str | None:
    """Return the text from a content item, or None if it's not a text block.

    Accepts both the dict shape (from the streaming path) and the Pydantic
    model shape (from the non-streaming path), since the Merge gateway
    normalises them differently.
    """
    if isinstance(item, dict):
        kind = item.get("type")
        text = item.get("text")
    else:
        kind = getattr(item, "type", None)
        text = getattr(item, "text", None)
    if kind != "text" or not isinstance(text, str):
        return None
    return text


def _extract_text(response) -> str:
    """Pull the human-readable text from a non-streaming response."""
    output = _get_attr(response, "output")
    if not isinstance(output, list):
        return ""
    parts: list[str] = []
    for item in output:
        content = _get_attr(item, "content")
        if not isinstance(content, list):
            continue
        for block in content:
            text = _text_field(block)
            if text:
                parts.append(text)
    return "".join(parts).strip()


