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
You are an experienced tarot reader doing a reading for a real person.

The querent has asked a specific question and drawn cards to answer it.
The question is the thing you are answering. The cards are the material.
Read the card for what it means, then bring that meaning back to the
question. If the card is reversed, the answer leans toward no, not yet,
or an inward turn. If upright, the answer leans yes, or it is available.

Weave the question through the whole reading. Give the answer directly,
early. End with one short paragraph on what to carry away.

Write in second person, present tense. Plain, direct, specific. Short
sentences. No em dashes. No hedging. No "the universe is telling you".
Use the querent's gender and relationship preference correctly when the
question touches relationships.
"""


# Thinking is enabled with a bounded budget so the model can reason from the
# question to the card and back. With thinking disabled, the model produces
# fluent generic card interpretations that don't answer the question — the
# user's core complaint. With thinking enabled at a modest budget, the model
# reasons "the user asked about love, the card is reversed, so the answer is
# no / not yet, and the reversal means X about how you're holding yourself."
#
# The Merge gateway requires budget_tokens > 0. We cap it at 1000 so the
# first token lands in ~1-2s instead of burning 4000+ tokens thinking.
THINKING_CONFIG = {"type": "enabled", "budget_tokens": 1000}


def _card_line(card, drawn) -> str:
    orientation = "reversed" if drawn.is_reversed else "upright"
    body = " ".join(drawn.body).strip()
    summary = drawn.summary
    return (
        f"- {drawn.position.title} — {card.name} ({orientation}): "
        f"{summary} {body}"
    )


def _question_category(question: str) -> str:
    """Classify the querent's question into a topic the model can anchor on.

    The card's stored meaning text is topic-specific (Four of Coins talks
    about money, Three of Swords about grief). When the question is about
    love but the card is a money card, the model needs to know the question
    is a love question so it can bridge 'scarcity' to 'emotional scarcity'
    instead of producing a literal money reading.
    """
    q = question.lower()
    love_words = ("love", "relationship", "partner", "date", "dating", "marry",
                  "marriage", "crush", "ex", "breakup", "find someone", "boyfriend",
                  "girlfriend", "husband", "wife", "gay", "lesbian", "drawn to",
                  "romance", "romantic", "meet someone", "soulmate")
    career_words = ("job", "career", "work", "promotion", "interview", "boss",
                    "salary", "raise", "business", "startup", "project", "colleague")
    choice_words = ("choose", "choice", "decide", "decision", "which", "option",
                    "either", "or should i", "should i take", "pick")
    health_words = ("health", "sick", "ill", "pain", "doctor", "exercise", "energy")
    if any(w in q for w in love_words):
        return "love and relationships"
    if any(w in q for w in career_words):
        return "career and work"
    if any(w in q for w in choice_words):
        return "a choice or decision"
    if any(w in q for w in health_words):
        return "health and wellbeing"
    return "life and general direction"


def _querent_context(reading: Reading) -> str:
    """Build the querent context block that opens the user message.

    Includes resonance, drawn-to, and any birth data the user gave. The
    LLM uses this to speak to the user correctly — a gay man and a
    straight woman get appropriately different dating language.
    """
    q = reading.querent
    parts: list[str] = []
    if q.name.strip():
        parts.append(f"The querent is {q.name}, age {q.age}.")
    parts.extend(_labeled_value("Gender", q.resonance, skip=("Unspecified",)))
    parts.extend(_labeled_value("Drawn to", q.drawn_to, skip=("Prefer not to say",)))
    if q.birth_date is not None:
        from app.domain.seeding import life_path
        parts.append(f"Date of birth: {q.birth_date.isoformat()} (life path {life_path(q.birth_date)}).")
    parts.extend(_labeled_value("Birth time", q.birth_time))
    parts.extend(_labeled_value("Birth place", q.birth_place))
    if reading.numerology is not None:
        parts.append(
            f"Numerology: name vibration {reading.numerology.name_value}, "
            f"day vibration {reading.numerology.day_of_year}."
        )
    return " ".join(parts)


def _labeled_value(label: str, value: str | None, skip: tuple[str, ...] = ()) -> list[str]:
    """Return ['Label: value.'] or []. Extracted to keep _querent_context under CC 9."""
    if not value or value in skip:
        return []
    return [f"{label}: {value}."]


def build_prompt(reading: Reading) -> str:
    """Compose the user message.

    Simple: the question, the querent, the cards. The model ties the card's
    meaning to the question. No structural gymnastics — trust the model.
    """
    question_block = (
        f"The querent asks: \"{reading.question}\"\n\n"
        if reading.question else ""
    )
    querent_context = _querent_context(reading)
    card_lines = "\n".join(_card_line(d.card, d) for d in reading.drawn)
    return (
        f"{question_block}"
        f"{querent_context}\n\n"
        f"{card_lines}\n\n"
        "Answer the querent's question using the card. Tie the card's "
        "meaning directly to what they asked. Give the answer early. "
        "Weave the question through the reading. End with a short "
        "paragraph on what to carry away."
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


