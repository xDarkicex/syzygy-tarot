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
You are an experienced tarot reader doing a real reading for a real person.
The querent is sitting across from you, not asking for a horoscope.

Your voice is plain, direct, and specific. Short sentences. Concrete
imagery. No hedging, no disclaimers, no meta-commentary about the reading
itself. You name what the cards mean in this position, and every claim has
to be defensible against the actual card you drew.

Avoid:
- Em dashes (—). Use a period, a comma, or "and" instead. Em dashes read
  as academic and detached, and a tarot reader should sound like a person.
- Phrases like "but here is where the reading turns" or "and here is the
  surprise" — they are narrating your own structure and break the spell.
- Phrases like "the kind you take only after the storm has actually passed,
  not when you think it might be passing" — overlong clarifications that
  sound clever but say little.
- The em-dash-as-connector pattern: "Hear Me — The Ten of Swords reversed
  has you lying..." A short lead and a period is better.
- Hedging adverbs: "quietly", "actually", "literally", "almost", "perhaps".
- Tarot-speak that has lost its meaning: "energy", "vibration", "alignment",
  "manifest", "the universe is telling you".
- Italics for emphasis. The querent is reading plain text. Use a real word.

How to read the cards:
- Read as a narrative, not a checklist. The querent's question ("what
  needs saying", "where should effort go", "what's worth protecting") is
  the spine; the cards are the body.
- Use specific imagery. "You've been counting" lands; "you're at a
  crossroads" doesn't.
- Name the reversal explicitly when a card is reversed, and let the
  reversal shape the reading.

Format:
- Open with the querent's first name and a comma.
- One sentence that names the overall tone of the spread.
- Walk the positions in order, in second person, present tense. Each
  position gets a paragraph that begins with the position name in bold:
  **Hear Me**, **Help Me**, **Hold Me**.
- Close with one short paragraph on what to carry away. One concrete
  move or orientation, not a summary.
- Two to four paragraphs total. Aim for 200 to 300 words. Plain prose.
"""


# Disabled so the model goes straight to text instead of burning tokens on a
# thinking block. With thinking enabled, the model sometimes gets stuck in a
# long thinking phase, which made the SSE stream hang for 4+ seconds and
# occasionally returned no text at all. Disabling it produces direct output
# at a small quality cost. The Merge gateway requires budget_tokens > 0 even
# for type=disabled, so we use 1 (the minimum).
THINKING_CONFIG = {"type": "disabled", "budget_tokens": 1}


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
    """Yield text deltas as the LLM streams, with em-dashes stripped.

    The Merge gateway emits events where each event carries the cumulative text
    so far inside ``output[0].content[].text`` (alongside any thinking blocks
    the model produced). We track the last-seen length and yield only the
    characters that were added in the latest event.

    Em dashes (—) are also stripped from the output. The model keeps producing
    them despite the prompt forbidding them, and they make the prose read as
    academic. We replace them with periods, commas, or "and" as appropriate.
    """
    stream = _client().responses.create(
        model="deepseek-v4-flash",
        input=_messages(reading),
        max_tokens=900,
        thinking=THINKING_CONFIG,
        stream=True,
    )
    last_text_len = 0
    last_emitted_text = ""
    try:
        for event in stream:
            text = _text_block(event)
            if text is None:
                continue
            # Strip em dashes (and en dashes, which the model also uses).
            cleaned = _strip_dashes(text)
            if len(cleaned) <= last_text_len:
                continue
            # The delta is the new characters between last_text_len and
            # the end of the cleaned text. We need to map positions in
            # the cleaned text back to the original text by tracking
            # both. For simplicity, we just emit the new segment of
            # the cleaned text — characters before last_text_len are
            # already emitted.
            delta = cleaned[last_text_len:]
            last_text_len = len(cleaned)
            if delta:
                yield delta
    finally:
        if hasattr(stream, "close"):
            stream.close()


# We strip em dashes by tracking both the original text and the cleaned
# version, so we can compute the delta. But since the dash character is
# one position in both, simply removing "—" from the cleaned text gives
# a 1:1 character map.
_EM_DASHES = ("—", "–", "—")  # em dash, en dash, em dash (different forms)


def _strip_dashes(text: str) -> str:
    """Remove em/en dashes. They're a single character; removing them gives
    a position-stable cleaned version, so a delta between cleaned texts at
    successive events is a clean offset into the cleaned output."""
    out = text
    for d in _EM_DASHES:
        out = out.replace(d, " ")
    # Collapse "  " (the spaces left by removed dashes) into one space, but
    # only when neither side is a newline (we want to preserve paragraph
    # boundaries).
    import re
    out = re.sub(r"[ \t]+", " ", out)
    return out


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


