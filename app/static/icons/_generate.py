"""Generate the 78 tarot icons as SVG files.

Run from the project root: ``python -m app.static.icons._generate``.

Design rules
------------
- All icons use ``fill="currentColor"`` or ``stroke="currentColor"`` so the card's
  accent colour drives the appearance via CSS.
- ViewBox is 100x140, matching the 5:7 card aspect ratio. The same SVG is used as both
  the corner index (scaled small) and the central watermark (scaled large + faded).
- Major arcana: one distinctive geometric mark per card.
- Minor arcana: suit symbol + rank pattern (pips 1-10, figures for court cards).
- File size target: <2KB per icon.
"""

from __future__ import annotations

import pathlib
from typing import Iterable

OUT = pathlib.Path(__file__).parent

CANVAS = 100
W = CANVAS
H = 140
STROKE = 1.6


def svg(body: str, title: str) -> str:
    """Wrap a body in the standard SVG header.

    The parent group sets both fill and stroke to currentColor so child elements can use
    whichever is appropriate via the shorthand attributes on the elements themselves.
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{title}" fill="currentColor" stroke="currentColor" '
        f'stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round">'
        f'<title>{title}</title>'
        f'{body}'
        f'</svg>'
    )


def translate(x: float, y: float) -> str:
    return f'transform="translate({x} {y})"'


# ─────── Major arcana ───────

MAJORS: dict[str, str] = {
    "The Fool": '<circle cx="50" cy="70" r="22" stroke-width="' + str(STROKE) + '"/>'
                '<path d="M 50 48 L 50 92" stroke-width="' + str(STROKE) + '"/>'
                '<circle cx="50" cy="40" r="3"/>'
                '<path d="M 44 96 L 56 96" stroke-width="' + str(STROKE) + '"/>',
    "The Magician": '<path d="M 30 50 C 30 35, 70 35, 70 50 C 70 65, 30 65, 30 50 C 30 35, 70 35, 70 50" stroke-width="' + str(STROKE) + '"/>'
                    '<path d="M 50 50 L 50 110" stroke-width="' + str(STROKE) + '"/>'
                    '<circle cx="50" cy="115" r="3"/>',
    "The High Priestess": '<path d="M 50 30 L 50 110" stroke-width="' + str(STROKE) + '"/>'
                          '<circle cx="50" cy="40" r="4"/>'
                          '<circle cx="50" cy="70" r="4"/>'
                          '<circle cx="50" cy="100" r="4"/>',
    "The Empress": '<circle cx="50" cy="70" r="26" stroke-width="' + str(STROKE) + '"/>'
                   '<path d="M 35 90 Q 50 105, 65 90" stroke-width="' + str(STROKE) + '"/>'
                   '<circle cx="50" cy="58" r="3"/>',
    "The Emperor": '<path d="M 30 45 L 70 45 L 70 95 L 30 95 Z" stroke-width="' + str(STROKE) + '"/>'
                   '<path d="M 35 45 L 35 35 L 65 35 L 65 45" stroke-width="' + str(STROKE) + '"/>'
                   '<circle cx="50" cy="65" r="4"/>',
    "The Hierophant": '<path d="M 50 35 L 30 50 L 50 65 L 70 50 Z" stroke-width="' + str(STROKE) + '"/>'
                      '<path d="M 40 75 L 40 105 M 60 75 L 60 105" stroke-width="' + str(STROKE) + '"/>'
                      '<path d="M 35 105 L 65 105" stroke-width="' + str(STROKE) + '"/>',
    "The Lovers": '<circle cx="35" cy="65" r="14" stroke-width="' + str(STROKE) + '"/>'
                  '<circle cx="65" cy="65" r="14" stroke-width="' + str(STROKE) + '"/>'
                  '<path d="M 50 35 L 50 100" stroke-width="' + str(STROKE) + '"/>',
    "The Chariot": '<path d="M 30 55 L 50 35 L 70 55 L 70 95 L 30 95 Z" stroke-width="' + str(STROKE) + '"/>'
                   '<circle cx="38" cy="60" r="3"/>'
                   '<circle cx="62" cy="60" r="3"/>'
                   '<path d="M 30 95 L 25 110 M 70 95 L 75 110 M 50 95 L 50 110" stroke-width="' + str(STROKE) + '"/>',
    "Strength": '<path d="M 30 70 C 30 50, 70 50, 70 70 C 70 90, 30 90, 30 70" stroke-width="' + str(STROKE) + '"/>'
                '<path d="M 50 50 L 50 100" stroke-width="' + str(STROKE) + '"/>'
                '<circle cx="50" cy="40" r="3"/>',
    "The Hermit": '<path d="M 50 35 L 50 95" stroke-width="' + str(STROKE) + '"/>'
                  '<path d="M 42 30 L 50 25 L 58 30 L 58 45 L 42 45 Z" stroke-width="' + str(STROKE) + '"/>'
                  '<circle cx="50" cy="115" r="5" stroke-width="' + str(STROKE) + '"/>'
                  '<path d="M 50 100 L 50 110 M 50 105 L 55 105 M 50 105 L 45 105" stroke-width="' + str(STROKE) + '"/>',
    "Wheel of Fortune": '<circle cx="50" cy="70" r="26" stroke-width="' + str(STROKE) + '"/>'
                        '<circle cx="50" cy="70" r="10" stroke-width="' + str(STROKE) + '"/>'
                        '<path d="M 50 30 L 50 40 M 50 100 L 50 110 M 24 70 L 34 70 M 66 70 L 76 70" stroke-width="' + str(STROKE) + '"/>'
                        '<path d="M 50 30 L 56 36 L 50 42 L 44 36 Z"/>',
    "Justice": '<path d="M 50 30 L 50 95" stroke-width="' + str(STROKE) + '"/>'
               '<path d="M 30 45 L 70 45 L 65 55 L 35 55 Z" stroke-width="' + str(STROKE) + '"/>'
               '<path d="M 30 95 L 70 95" stroke-width="' + str(STROKE) + '"/>'
               '<path d="M 45 60 L 45 90 M 55 60 L 55 90 M 45 90 L 55 90" stroke-width="' + str(STROKE) + '"/>',
    "The Hanged Man": '<circle cx="50" cy="40" r="8" stroke-width="' + str(STROKE) + '"/>'
                      '<path d="M 42 50 L 58 50" stroke-width="' + str(STROKE) + '"/>'
                      '<path d="M 50 48 L 50 100" stroke-width="' + str(STROKE) + '"/>'
                      '<path d="M 50 100 L 30 115" stroke-width="' + str(STROKE) + '"/>',
    "Death": '<path d="M 50 25 L 50 110" stroke-width="' + str(STROKE) + '"/>'
             '<path d="M 30 65 C 40 50, 60 50, 70 65 L 50 80 Z" stroke-width="' + str(STROKE) + '"/>'
             '<circle cx="50" cy="25" r="3"/>',
    "Temperance": '<path d="M 30 55 L 30 90 L 70 90 L 70 55" stroke-width="' + str(STROKE) + '"/>'
                  '<path d="M 25 55 C 35 40, 65 40, 75 55" stroke-width="' + str(STROKE) + '"/>'
                  '<path d="M 45 75 L 55 75" stroke-width="' + str(STROKE) + '"/>',
    "The Devil": '<path d="M 50 30 L 50 80" stroke-width="' + str(STROKE) + '"/>'
                 '<path d="M 35 40 L 50 30 L 65 40" stroke-width="' + str(STROKE) + '"/>'
                 '<circle cx="50" cy="95" r="14" stroke-width="' + str(STROKE) + '"/>'
                 '<path d="M 40 105 L 50 95 L 60 105" stroke-width="' + str(STROKE) + '"/>',
    "The Tower": '<path d="M 40 30 L 40 70 L 35 75 L 40 80 L 40 110" stroke-width="' + str(STROKE) + '"/>'
                 '<path d="M 60 30 L 60 70 L 65 75 L 60 80 L 60 110" stroke-width="' + str(STROKE) + '"/>'
                 '<path d="M 35 30 L 65 30" stroke-width="' + str(STROKE) + '"/>'
                 '<path d="M 30 60 L 70 60" stroke-width="' + str(STROKE) + '"/>',
    "The Star": '<path d="M 50 30 L 50 110" stroke-width="' + str(STROKE) + '"/>'
                '<path d="M 30 50 L 70 50" stroke-width="' + str(STROKE) + '"/>'
                '<path d="M 50 30 L 44 50 M 50 30 L 56 50 M 30 50 L 44 50 M 70 50 L 56 50" stroke-width="' + str(STROKE) + '"/>'
                '<circle cx="50" cy="50" r="3"/>',
    "The Moon": '<path d="M 30 70 A 20 20 0 1 0 70 70 A 16 16 0 1 1 30 70" stroke-width="' + str(STROKE) + '"/>'
                '<circle cx="50" cy="50" r="2"/>'
                '<circle cx="35" cy="40" r="2"/>'
                '<circle cx="65" cy="40" r="2"/>',
    "The Sun": '<circle cx="50" cy="70" r="20" stroke-width="' + str(STROKE) + '"/>'
               '<circle cx="50" cy="70" r="8"/>'
               '<path d="M 50 30 L 50 38 M 50 102 L 50 110 M 10 70 L 18 70 M 82 70 L 90 70" stroke-width="' + str(STROKE) + '"/>'
               '<path d="M 22 42 L 28 48 M 72 92 L 78 98 M 22 98 L 28 92 M 72 48 L 78 42" stroke-width="' + str(STROKE) + '"/>',
    "Judgement": '<path d="M 20 90 L 50 70 L 80 90" stroke-width="' + str(STROKE) + '"/>'
                 '<path d="M 35 50 L 35 70 M 50 45 L 50 65 M 65 50 L 65 70" stroke-width="' + str(STROKE) + '"/>'
                 '<path d="M 30 50 L 40 50 M 45 45 L 55 45 M 60 50 L 70 50" stroke-width="' + str(STROKE) + '"/>',
    "The World": '<circle cx="50" cy="70" r="26" stroke-width="' + str(STROKE) + '"/>'
                 '<path d="M 30 60 Q 40 50, 50 60 Q 60 70, 70 60" stroke-width="' + str(STROKE) + '"/>'
                 '<path d="M 30 80 Q 40 90, 50 80 Q 60 70, 70 80" stroke-width="' + str(STROKE) + '"/>'
                 '<circle cx="50" cy="50" r="2"/>',
}


# ─────── Minor arcana: pip patterns ───────

PIP_DOT = '<circle cx="{x}" cy="{y}" r="4"/>'


def pip(x: float, y: float) -> str:
    return PIP_DOT.format(x=x, y=y)


# Pip layouts as data: a list of (x, y) tuples per count. This keeps the generator
# pure-data and avoids an 11-branch if-elif chain.
PIP_LAYOUTS: dict[int, tuple[tuple[float, float], ...]] = {
    1:  ((50, 70),),
    2:  ((50, 50), (50, 90)),
    3:  ((50, 45), (50, 70), (50, 95)),
    4:  ((35, 50), (65, 50), (35, 90), (65, 90)),
    5:  ((35, 50), (65, 50), (50, 70), (35, 90), (65, 90)),
    6:  ((35, 45), (65, 45), (35, 70), (65, 70), (35, 95), (65, 95)),
    7:  ((35, 42), (65, 42), (50, 60), (35, 78), (65, 78), (35, 100), (65, 100)),
    8:  ((35, 42), (65, 42), (50, 60), (35, 78), (65, 78), (50, 96), (35, 96), (65, 96)),
    9:  ((35, 42), (65, 42), (50, 56), (35, 70), (65, 70), (50, 84), (35, 98), (65, 98), (50, 105)),
    10: ((35, 38), (65, 38), (50, 48), (35, 58), (65, 58), (35, 78), (65, 78), (50, 88), (35, 98), (65, 98)),
}


def pip_grid(count: int, suit: str) -> str:
    """Layout pips 1-10 in the canonical tarot arrangement."""
    return "".join(pip(x, y) for x, y in PIP_LAYOUTS[count])


# ─────── Minor arcana: suit motifs ───────

def suit_glyph(suit: str, x: float, y: float, scale: float = 1.0) -> str:
    """A small suit marker used inside the pips for non-coin suits."""
    cx, cy = x, y
    if suit == "wands":
        return f'<path d="M {cx - 4 * scale} {cy - 10 * scale} L {cx + 4 * scale} {cy - 10 * scale} L {cx + 4 * scale} {cy + 10 * scale} L {cx - 4 * scale} {cy + 10 * scale} Z" stroke-width="{STROKE}"/>' \
               f'<path d="M {cx} {cy - 10 * scale} L {cx} {cy - 16 * scale} M {cx - 3 * scale} {cy - 13 * scale} L {cx + 3 * scale} {cy - 13 * scale}" stroke-width="{STROKE}"/>'
    if suit == "cups":
        return f'<path d="M {cx - 8 * scale} {cy - 5 * scale} L {cx + 8 * scale} {cy - 5 * scale} L {cx + 6 * scale} {cy + 8 * scale} L {cx - 6 * scale} {cy + 8 * scale} Z" stroke-width="{STROKE}"/>' \
               f'<path d="M {cx - 4 * scale} {cy + 8 * scale} L {cx + 4 * scale} {cy + 8 * scale} L {cx + 4 * scale} {cy + 12 * scale} L {cx - 4 * scale} {cy + 12 * scale} Z" fill="currentColor"/>'
    if suit == "swords":
        return f'<path d="M {cx} {cy - 12 * scale} L {cx} {cy + 10 * scale}" stroke-width="{STROKE}"/>' \
               f'<path d="M {cx - 6 * scale} {cy + 4 * scale} L {cx + 6 * scale} {cy + 4 * scale}" stroke-width="{STROKE}"/>' \
               f'<circle cx="{cx}" cy="{cy + 12 * scale}" r="2"/>'
    return pip(cx, cy)


def minor_card_body(suit: str, rank: int) -> str:
    """Compose a minor-arcana card body: suit glyph + pip pattern + frame."""
    frame = '<rect x="6" y="6" width="88" height="128" rx="3" stroke-width="' + str(STROKE) + '"/>'
    if rank == 1:  # Ace: a single large suit glyph
        return frame + suit_glyph(suit, 50, 70, scale=2.2)
    if 2 <= rank <= 10:
        pip_glyph = suit_glyph if suit == "coins" else lambda s, x, y, scale=1.0: suit_glyph(s, x, y, scale=0.7)
        return frame + pip_grid(rank, suit)
    return frame + court_card(suit, rank)


# ─────── Court cards ───────

def court_card(suit: str, rank: int) -> str:
    """Stylised seated/standing figure for Page/Knight/Queen/King."""
    # Slight pose variation by rank
    if rank == 11:  # Page: small figure, holding suit object
        figure = (
            '<circle cx="50" cy="50" r="8" stroke-width="' + str(STROKE) + '"/>'
            '<path d="M 50 58 L 50 95" stroke-width="' + str(STROKE) + '"/>'
            '<path d="M 50 70 L 65 80 M 50 70 L 35 80" stroke-width="' + str(STROKE) + '"/>'
            '<path d="M 40 95 L 60 95" stroke-width="' + str(STROKE) + '"/>'
        )
    elif rank == 12:  # Knight: standing figure with legs
        figure = (
            '<circle cx="50" cy="45" r="8" stroke-width="' + str(STROKE) + '"/>'
            '<path d="M 50 53 L 50 90" stroke-width="' + str(STROKE) + '"/>'
            '<path d="M 50 65 L 38 78 L 38 100" stroke-width="' + str(STROKE) + '"/>'
            '<path d="M 50 65 L 62 78 L 62 100" stroke-width="' + str(STROKE) + '"/>'
        )
    elif rank == 13:  # Queen: figure with crown
        figure = (
            '<path d="M 42 38 L 42 32 L 50 35 L 58 32 L 58 38" stroke-width="' + str(STROKE) + '"/>'
            '<circle cx="50" cy="50" r="8" stroke-width="' + str(STROKE) + '"/>'
            '<path d="M 36 70 Q 50 65, 64 70 L 60 100 L 40 100 Z" stroke-width="' + str(STROKE) + '"/>'
        )
    else:  # King: figure with crown and larger frame
        figure = (
            '<path d="M 40 40 L 40 32 L 50 35 L 60 32 L 60 40" stroke-width="' + str(STROKE) + '"/>'
            '<circle cx="50" cy="52" r="9" stroke-width="' + str(STROKE) + '"/>'
            '<path d="M 32 72 L 68 72 L 64 105 L 36 105 Z" stroke-width="' + str(STROKE) + '"/>'
        )
    # Embed a small suit glyph near the figure
    motif = suit_glyph(suit, 50, 118, scale=0.9)
    return figure + motif


# ─────── Main ───────

def iter_card_names() -> Iterable[tuple[str, str]]:
    """Yield (slug, svg_string) for every card in the deck."""
    for slug, name in sorted({(c["slug"], c["name"]) for c in _load_cards()}, key=lambda t: t[0]):
        yield _build(slug, name)


def _load_cards():
    import json
    from pathlib import Path
    path = Path(__file__).parent.parent.parent / "data" / "cards.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _build(slug: str, name: str) -> tuple[str, str]:
    title = name
    if name in MAJORS:
        body = svg(MAJORS[name], title)
    else:
        rank_word, _, suit_word = name.partition(" of ")
        suit = suit_word.lower()
        rank_map = {
            "Ace": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5,
            "Six": 6, "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10,
            "Page": 11, "Knight": 12, "Queen": 13, "King": 14,
        }
        rank = rank_map[rank_word]
        body = svg(minor_card_body(suit, rank), title)
    return slug, body


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    total_bytes = 0
    for slug, body in iter_card_names():
        (OUT / f"{slug}.svg").write_text(body, encoding="utf-8")
        written += 1
        total_bytes += len(body)
    print(f"wrote {written} icons, {total_bytes / 1024:.1f} KB total, {total_bytes // max(written, 1)} bytes avg")


if __name__ == "__main__":
    main()
