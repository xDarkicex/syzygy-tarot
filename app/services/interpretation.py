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

When the querent brought a question, the reading answers that question.
The question is not a suggestion, it is the focus. Answer it directly.
The cards always address the question through the reader's eye; that is
how tarot works.

When the question is a yes/no ("will I meet X", "should I do Y"):
- Upright card = yes, with the card's own texture.
- Reversed card = no, or "not yet" — also with the card's own texture.
- The answer comes from the card's orientation, not from your
  invention. The card says what the yes or no means.

When the question is open-ended ("what should I do about X", "how is
this going"):
- Open with the card's actual message, then name how it answers the
  question. The card always has something to say. Find the bridge
  between the card's image and the querent's situation. That bridge
  is the reading.

When the question is about a person or relationship:
- Use the querent's gender and relationship preference correctly. A gay
  man asking about connection wants reading that names the kind of person
  he is drawn to, in his own language, without translation. A straight
  woman asking the same question wants different language. If the querent
  said they are drawn to men, use that; if women, use that. Don't
  default to heteronormative language, don't default to assuming anyone.

Avoid:
- Em dashes (—). Use a period, a comma, or "and" instead.
- Phrases like "but here is where the reading turns" or "and here is the
  surprise" — narrating your own structure.
- Overlong clarifications that sound clever but say little.
- Hedging adverbs: "quietly", "actually", "literally", "almost", "perhaps".
- Tarot-speak that has lost its meaning: "energy", "vibration", "alignment",
  "manifest", "the universe is telling you".
- Italics for emphasis. Plain text. Use a real word.

How to read the cards:
- Read as a narrative, not a checklist. The querent's question is the
  spine; the cards are the body.
- Use specific imagery. Find the bridge between the card's image and
  the querent's situation. That bridge IS the reading.
- Name the reversal explicitly when a card is reversed, and let the
  reversal shape the reading.

Format:
- If the querent asked a question, your opening sentence names the
  question and the card together. Example: "Gentry, you asked
  whether the love of your life is close, and the Hanged Man says..."
- If the question is yes/no and the card is reversed, the opening
  should make the no clear, but with the card's own texture. "Gentry,
  the Hanged Man reversed says no, not today — but the no is about
  forcing, not about the meeting itself."
- Otherwise, open with the querent's first name and a comma.
- One sentence that names the overall tone of the spread.
- For a MULTI-card spread (3+ cards): walk the positions in order, in
  second person, present tense. Each position gets a paragraph that
  begins with the position name in bold: **Hear Me**, **Help Me**,
  **Hold Me**.
- For a SINGLE-card spread: do NOT use position-name headings like
  **Hear Me** or **Help Me**. The card has one position and its title
  is "The Card". Write continuous paragraphs with no bold headings,
  following the question-aware structure in the user's message.
- Close with one short paragraph on what to carry away. If a question
  was asked, the carry-away is the direct answer.
- Two to four paragraphs total. Aim for 200 to 300 words. Plain prose.
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


def _card_line(card, drawn, category: str | None = None) -> str:
    orientation = "reversed" if drawn.is_reversed else "upright"
    body = " ".join(drawn.body).strip()
    summary = drawn.summary
    base = f"- {drawn.position.title} — {card.name} ({orientation}): {summary} {body}"
    if category == "love and relationships" and card.suit == "coins":
        # The coin cards are stored with money-only meanings. When the
        # question is about love, re-angle the core tension in relational
        # terms so the model has a bridge instead of a money reading.
        base += (
            " This card's imagery about money and resources should be read "
            "as emotional and relational: holding tight is not letting anyone "
            "in, scarcity is fear of being unlovable, giving too freely is "
            "over-giving to feel wanted, hoarding is guardedness that keeps "
            "partners at arm's length. The fear here is about love, not money."
        )
    return base


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
    """Compose the user message that asks for a combined interpretation.

    The question, if any, is the headline — the model sees it first. Cards
    speak to the question; the model is instructed to address the question
    in the opening sentence, not in a closing paragraph where it can be
    ignored.
    """
    spread_name = reading.spread.name
    category = _question_category(reading.question) if reading.question else None
    card_lines = "\n".join(_card_line(d.card, d, category) for d in reading.drawn)
    querent_context = _querent_context(reading)
    category_block = (
        f"The querent's question is about {category}.\n\n"
        if category else ""
    )
    question_block = (
        f"The querent asked the cards: \"{reading.question}\"\n\n"
        if reading.question else ""
    )
    # For a single-card draw with a question, the model often defaults to a
    # generic card interpretation. Force a different structure: the question
    # is the spine of every paragraph, the card informs each section, and
    # the answer is the close.
    if reading.question and len(reading.drawn) == 1:
        answer_format = (
            "Write three short paragraphs. The question is the spine of "
            "every paragraph. The card is the answer. The querent's question "
            "is not a topic to mention, it is the question to answer.\n\n"
            "1. THE ANSWER. Open with the querent's name and restate their "
            "question in their own language. Then give the direct answer "
            "in the FIRST sentence of this paragraph. If the question is "
            "yes/no, the answer comes from the card's orientation: "
            "upright = yes, reversed = no or not yet. The answer is one "
            "sentence and it directly answers the question they asked — "
            "for 'will I find love soon', 'yes, the cup is full and the "
            "wish is at the table' is an answer; 'the card's message is "
            "about satisfaction' is not an answer. Do not hedge. Do not "
            "say 'if your question was about X'. The question IS about X. "
            "Answer it.\n\n"
            "2. THE BRIDGE. Show specifically how the card answers the "
            "question they asked. The card's imagery is the bridge between "
            "their situation and the answer. Name the specific image — "
            "the cup on the table, the man hanging by one foot, the "
            "upright coin or the loose one — and how that image is the "
            "answer to their question about love / career / a person / "
            "a choice. The bridge must connect the card to THEIR question, "
            "not to a generic reading.\n\n"
            "3. WHAT TO CARRY. One short paragraph on what to do with "
            "the answer. The carry-away is the action that flows from the "
            "answer — not a summary, not a recap. For love questions, the "
            "carry-away is the move that opens or closes the door; for "
            "career questions, it is the move that lands or waits; for a "
            "choice, it is the move that commits or steps back. One "
            "sentence, grounded in the card's imagery.\n"
        )
    else:
        answer_format = (
            "Write the combined meaning. If the querent asked a question, "
            "open with a sentence that names the question and the card "
            "together, then walk the positions in order and show how they "
            "speak to each other, then close with a short paragraph on "
            "what to carry away. The carry-away should be the direct "
            "answer to the question when one was asked. Two to four short "
            "paragraphs total, grounded in the specific cards."
        )
    return (
        f"{question_block}"
        f"{category_block}"
        f"Read the following {spread_name.lower()}. {querent_context}\n\n"
        f"{card_lines}\n\n"
        f"{answer_format}"
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


