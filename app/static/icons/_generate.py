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

    The default is ``fill="none" stroke="currentColor"`` so structural lines render as
    outlines. Children that should be solid (pips, dots) get an explicit
    ``fill="currentColor" stroke="none"`` override.
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{title}" fill="none" stroke="currentColor" '
        f'stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round">'
        f'<title>{title}</title>'
        f'{body}'
        f'</svg>'
    )


# ─────── Major arcana ───────

MAJORS: dict[str, str] = {
    "The Fool": '<circle cx="50" cy="70" r="22"/>'
                '<path d="M 50 48 L 50 92"/>'
                '<circle cx="50" cy="40" r="3" fill="currentColor" stroke="none"/>'
                '<path d="M 44 96 L 56 96"/>',
    "The Magician": '<path d="M 30 50 C 30 35, 70 35, 70 50 C 70 65, 30 65, 30 50 C 30 35, 70 35, 70 50"/>'
                    '<path d="M 50 50 L 50 110"/>'
                    '<circle cx="50" cy="115" r="3" fill="currentColor" stroke="none"/>',
    "The High Priestess": '<path d="M 50 30 L 50 110"/>'
                          '<circle cx="50" cy="40" r="4" fill="currentColor" stroke="none"/>'
                          '<circle cx="50" cy="70" r="4" fill="currentColor" stroke="none"/>'
                          '<circle cx="50" cy="100" r="4" fill="currentColor" stroke="none"/>',
    "The Empress": '<circle cx="50" cy="70" r="26"/>'
                   '<path d="M 35 90 Q 50 105, 65 90"/>'
                   '<circle cx="50" cy="58" r="3" fill="currentColor" stroke="none"/>',
    "The Emperor": '<path d="M 30 45 L 70 45 L 70 95 L 30 95 Z"/>'
                   '<path d="M 35 45 L 35 35 L 65 35 L 65 45"/>'
                   '<circle cx="50" cy="65" r="4" fill="currentColor" stroke="none"/>',
    "The Hierophant": '<path d="M 50 35 L 30 50 L 50 65 L 70 50 Z"/>'
                      '<path d="M 40 75 L 40 105 M 60 75 L 60 105"/>'
                      '<path d="M 35 105 L 65 105"/>',
    "The Lovers": '<circle cx="35" cy="65" r="14"/>'
                  '<circle cx="65" cy="65" r="14"/>'
                  '<path d="M 50 35 L 50 100"/>',
    "The Chariot": '<path d="M 30 55 L 50 35 L 70 55 L 70 95 L 30 95 Z"/>'
                   '<circle cx="38" cy="60" r="3" fill="currentColor" stroke="none"/>'
                   '<circle cx="62" cy="60" r="3" fill="currentColor" stroke="none"/>'
                   '<path d="M 30 95 L 25 110 M 70 95 L 75 110 M 50 95 L 50 110"/>',
    "Strength": '<path d="M 30 70 C 30 50, 70 50, 70 70 C 70 90, 30 90, 30 70"/>'
                '<path d="M 50 50 L 50 100"/>'
                '<circle cx="50" cy="40" r="3" fill="currentColor" stroke="none"/>',
    "The Hermit": '<path d="M 50 35 L 50 95"/>'
                  '<path d="M 42 30 L 50 25 L 58 30 L 58 45 L 42 45 Z"/>'
                  '<circle cx="50" cy="115" r="5"/>'
                  '<path d="M 50 100 L 50 110 M 50 105 L 55 105 M 50 105 L 45 105"/>',
    "Wheel of Fortune": '<circle cx="50" cy="70" r="26"/>'
                        '<circle cx="50" cy="70" r="10"/>'
                        '<path d="M 50 30 L 50 40 M 50 100 L 50 110 M 24 70 L 34 70 M 66 70 L 76 70"/>'
                        '<path d="M 50 30 L 56 36 L 50 42 L 44 36 Z" fill="currentColor" stroke="none"/>',
    "Justice": '<path d="M 50 30 L 50 95"/>'
               '<path d="M 30 45 L 70 45 L 65 55 L 35 55 Z"/>'
               '<path d="M 30 95 L 70 95"/>'
               '<path d="M 45 60 L 45 90 M 55 60 L 55 90 M 45 90 L 55 90"/>',
    "The Hanged Man": '<circle cx="50" cy="40" r="8"/>'
                      '<path d="M 42 50 L 58 50"/>'
                      '<path d="M 50 48 L 50 100"/>'
                      '<path d="M 50 100 L 30 115"/>',
    "Death": '<path d="M 50 25 L 50 110"/>'
             '<path d="M 30 65 C 40 50, 60 50, 70 65 L 50 80 Z"/>'
             '<circle cx="50" cy="25" r="3" fill="currentColor" stroke="none"/>',
    "Temperance": '<path d="M 30 55 L 30 90 L 70 90 L 70 55"/>'
                  '<path d="M 25 55 C 35 40, 65 40, 75 55"/>'
                  '<path d="M 45 75 L 55 75"/>',
    "The Devil": '<path d="M 50 30 L 50 80"/>'
                 '<path d="M 35 40 L 50 30 L 65 40"/>'
                 '<circle cx="50" cy="95" r="14"/>'
                 '<path d="M 40 105 L 50 95 L 60 105"/>',
    "The Tower": '<path d="M 40 30 L 40 70 L 35 75 L 40 80 L 40 110"/>'
                 '<path d="M 60 30 L 60 70 L 65 75 L 60 80 L 60 110"/>'
                 '<path d="M 35 30 L 65 30"/>'
                 '<path d="M 30 60 L 70 60"/>',
    "The Star": '<path d="M 50 30 L 50 110"/>'
                '<path d="M 30 50 L 70 50"/>'
                '<path d="M 50 30 L 44 50 M 50 30 L 56 50 M 30 50 L 44 50 M 70 50 L 56 50"/>'
                '<circle cx="50" cy="50" r="3" fill="currentColor" stroke="none"/>',
    "The Moon": '<path d="M 30 70 A 20 20 0 1 0 70 70 A 16 16 0 1 1 30 70"/>'
                '<circle cx="50" cy="50" r="2" fill="currentColor" stroke="none"/>'
                '<circle cx="35" cy="40" r="2" fill="currentColor" stroke="none"/>'
                '<circle cx="65" cy="40" r="2" fill="currentColor" stroke="none"/>',
    "The Sun": '<circle cx="50" cy="70" r="20"/>'
               '<circle cx="50" cy="70" r="8" fill="currentColor" stroke="none"/>'
               '<path d="M 50 30 L 50 38 M 50 102 L 50 110 M 10 70 L 18 70 M 82 70 L 90 70"/>'
               '<path d="M 22 42 L 28 48 M 72 92 L 78 98 M 22 98 L 28 92 M 72 48 L 78 42"/>',
    "Judgement": '<path d="M 20 90 L 50 70 L 80 90"/>'
                 '<path d="M 35 50 L 35 70 M 50 45 L 50 65 M 65 50 L 65 70"/>'
                 '<path d="M 30 50 L 40 50 M 45 45 L 55 45 M 60 50 L 70 50"/>',
    "The World": '<circle cx="50" cy="70" r="26"/>'
                 '<path d="M 30 60 Q 40 50, 50 60 Q 60 70, 70 60"/>'
                 '<path d="M 30 80 Q 40 90, 50 80 Q 60 70, 70 80"/>'
                 '<circle cx="50" cy="50" r="2" fill="currentColor" stroke="none"/>',
}


# ─────── Minor arcana: suit glyph generators ───────
# Each function returns the SVG for ONE instance of the suit motif, centred at
# (x, y) with the given scale. The Ace is just one large central instance. Ranks
# 2-10 are composed of N instances arranged per layout below.

def wand(x: float, y: float, scale: float = 1.0) -> str:
    """A flame-tipped staff."""
    s = scale
    return (
        f'<path d="M {x - 2.5 * s} {y - 14 * s} L {x + 2.5 * s} {y - 14 * s} L {x + 2.5 * s} {y + 14 * s} L {x - 2.5 * s} {y + 14 * s} Z"/>'
        f'<path d="M {x} {y - 14 * s} L {x - 4 * s} {y - 22 * s} M {x} {y - 14 * s} L {x + 4 * s} {y - 22 * s} M {x - 3 * s} {y - 18 * s} L {x + 3 * s} {y - 18 * s}"/>'
    )


def cup(x: float, y: float, scale: float = 1.0) -> str:
    """A chalice with water-line and stem."""
    s = scale
    return (
        f'<path d="M {x - 9 * s} {y - 6 * s} Q {x} {y - 14 * s}, {x + 9 * s} {y - 6 * s} L {x + 6 * s} {y + 6 * s} L {x - 6 * s} {y + 6 * s} Z"/>'
        f'<path d="M {x - 5 * s} {y - 6 * s} Q {x} {y - 12 * s}, {x + 5 * s} {y - 6 * s}"/>'
        f'<path d="M {x - 2 * s} {y + 6 * s} L {x + 2 * s} {y + 6 * s} L {x + 3 * s} {y + 12 * s} L {x - 3 * s} {y + 12 * s} Z"/>'
        f'<path d="M {x - 6 * s} {y + 12 * s} L {x + 6 * s} {y + 12 * s}"/>'
    )


def sword(x: float, y: float, scale: float = 1.0) -> str:
    """A double-edged blade with crossguard and pommel."""
    s = scale
    return (
        f'<path d="M {x} {y - 14 * s} L {x} {y + 8 * s}"/>'
        f'<path d="M {x - 1.5 * s} {y - 10 * s} L {x + 1.5 * s} {y - 10 * s}"/>'
        f'<path d="M {x - 7 * s} {y + 6 * s} L {x + 7 * s} {y + 6 * s}"/>'
        f'<path d="M {x - 7 * s} {y + 6 * s} L {x - 7 * s} {y + 10 * s} M {x + 7 * s} {y + 6 * s} L {x + 7 * s} {y + 10 * s}"/>'
        f'<circle cx="{x}" cy="{y + 12 * s}" r="{2 * s}" fill="currentColor" stroke="none"/>'
    )


def coin(x: float, y: float, scale: float = 1.0) -> str:
    """A coin: outer ring with a small inner detail."""
    s = scale
    return (
        f'<circle cx="{x}" cy="{y}" r="{8 * s}"/>'
        f'<circle cx="{x}" cy="{y}" r="{4 * s}"/>'
    )


SUIT_GLYPH = {"wands": wand, "cups": cup, "swords": sword, "coins": coin}


# Canonical pip layouts: positions for ranks 1-10. Each entry is a tuple of
# (x, y) centres. Ranks use either 1, 2, 3 columns of 2/3/4 entries, with the
# centre column optionally used for 5/7/9/10.
LAYOUTS: dict[int, tuple[tuple[float, float], ...]] = {
    1:  ((50, 70),),
    2:  ((32, 70), (68, 70)),
    3:  ((50, 38), (32, 70), (68, 70)),  # one above, two below
    3:  ((50, 70),),  # placeholder; overridden below to symmetric
}
# Reassign 3..10 with a clean symmetric pip pattern.
LAYOUTS = {
    1:  ((50, 70),),
    2:  ((32, 70), (68, 70)),
    3:  ((50, 70),),  # not used; see LAYOUT_ODD
    4:  ((32, 45), (68, 45), (32, 95), (68, 95)),
    5:  ((32, 45), (68, 45), (50, 70), (32, 95), (68, 95)),
    6:  ((32, 40), (68, 40), (32, 70), (68, 70), (32, 100), (68, 100)),
    7:  ((32, 36), (68, 36), (50, 53), (32, 70), (68, 70), (32, 87), (68, 104)),
    8:  ((32, 36), (68, 36), (50, 53), (32, 70), (68, 70), (50, 87), (32, 104), (68, 104)),
    9:  ((32, 36), (68, 36), (32, 60), (68, 60), (50, 70), (32, 80), (68, 80), (32, 104), (68, 104)),
    10: ((32, 30), (68, 30), (32, 52), (68, 52), (50, 62), (32, 78), (68, 78), (50, 88), (32, 100), (68, 100)),
}
# 3 and 7 with the classic single-centre arrangement
LAYOUTS[3] = ((50, 40), (32, 70), (68, 70), (50, 100))
LAYOUTS[7] = ((32, 34), (68, 34), (50, 52), (32, 70), (68, 70), (32, 88), (68, 88))
LAYOUTS[9] = ((32, 34), (68, 34), (32, 56), (68, 56), (50, 70), (32, 84), (68, 84), (32, 106), (68, 106))


def minor_card_body(suit: str, rank: int) -> str:
    """Compose a minor-arcana card body."""
    frame = '<rect x="6" y="6" width="88" height="128" rx="3"/>'
    glyph = SUIT_GLYPH[suit]
    if rank == 1:
        return frame + glyph(50, 70, scale=2.4)
    if 2 <= rank <= 10:
        positions = LAYOUTS[rank]
        scale = 0.65 if rank >= 6 else 0.8
        return frame + "".join(glyph(x, y, scale=scale) for x, y in positions)
    return frame + court_card(suit, rank)


# ─────── Court cards ───────

def court_card(suit: str, rank: int) -> str:
    """Page/Knight/Queen/King with the figure holding the suit motif."""
    glyph = SUIT_GLYPH[suit]
    if rank == 11:  # Page: a small standing figure holding the motif
        figure = (
            '<circle cx="50" cy="55" r="6"/>'
            '<path d="M 50 61 L 50 92"/>'
            '<path d="M 50 70 L 38 82"/>'
            '<path d="M 50 70 L 62 82"/>'
            '<path d="M 44 92 L 56 92"/>'
        )
        motif = glyph(50, 50, scale=0.55)  # small motif above head
    elif rank == 12:  # Knight: figure on horseback? simpler: standing with crossed legs
        figure = (
            '<circle cx="50" cy="50" r="6"/>'
            '<path d="M 50 56 L 50 95"/>'
            '<path d="M 50 65 L 38 80 L 40 100"/>'
            '<path d="M 50 65 L 62 80 L 60 100"/>'
            '<path d="M 50 70 L 70 60"/>'
        )
        motif = glyph(72, 50, scale=0.55)
    elif rank == 13:  # Queen: seated figure
        figure = (
            '<path d="M 42 44 L 42 38 L 50 40 L 58 38 L 58 44"/>'  # crown
            '<circle cx="50" cy="54" r="6"/>'
            '<path d="M 36 75 Q 50 68, 64 75 L 60 100 L 40 100 Z"/>'  # dress
            '<path d="M 50 60 L 50 70"/>'  # neck
        )
        motif = glyph(50, 92, scale=0.7)  # motif on lap
    else:  # King: enthroned
        figure = (
            '<path d="M 38 46 L 38 38 L 50 41 L 62 38 L 62 46"/>'  # larger crown
            '<path d="M 42 40 L 42 35 M 50 38 L 50 33 M 58 40 L 58 35"/>'
            '<circle cx="50" cy="56" r="6"/>'
            '<path d="M 30 80 L 70 80 L 64 105 L 36 105 Z"/>'  # throne
        )
        motif = glyph(50, 92, scale=0.7)
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
