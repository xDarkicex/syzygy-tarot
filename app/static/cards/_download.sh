"""Download all 78 public-domain Rider-Waite-Smith card images.

Source: nishshoko/astra-cards (public domain in the US, original 1909 RWS art).
Run from the project root: ``python -m app.static.cards._download``.

After download, this script converts to JPEG and resizes to 500px max edge for
~70KB per image (~5MB total).
"""

import subprocess
import sys
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/nishshoko/astra-cards/main"
OUT = Path(__file__).parent
MAJOR_NAMES = [
    "the-fool", "the-magician", "the-high-priestess", "the-empress",
    "the-emperor", "the-hierophant", "the-lovers", "the-chariot",
    "strength", "the-hermit", "wheel-of-fortune", "justice",
    "the-hanged-man", "death", "temperance", "the-devil", "the-tower",
    "the-star", "the-moon", "the-sun", "judgement", "the-world",
]
RANK_WORDS = ["ace", "two", "three", "four", "five", "six", "seven", "eight",
              "nine", "ten", "page", "knight", "queen", "king"]
SUITS = {"wands": "wands", "cups": "cups", "swords": "swords", "coins": "pents"}


def slugs_and_sources():
    for i, name in enumerate(MAJOR_NAMES):
        yield name, f"major_{i:02d}"
    for suit, abbrev in SUITS.items():
        for i, rank in enumerate(RANK_WORDS, start=1):
            yield f"{rank}-of-{suit}", f"{abbrev}_{i:02d}"


def fetch_one(slug: str, source: str) -> bool:
    jpg = OUT / f"{slug}.jpg"
    if jpg.exists():
        return True
    webp = OUT / f"{source}.webp"
    try:
        urllib.request.urlretrieve(f"{RAW}/{source}.webp", webp)
    except Exception as exc:
        print(f"  download failed {slug}: {exc}")
        return False
    r = subprocess.run(
        ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82",
         str(webp), "--out", str(jpg)],
        capture_output=True, text=True,
    )
    webp.unlink(missing_ok=True)
    if r.returncode != 0:
        print(f"  sips failed {slug}: {r.stderr[:200]}")
        return False
    return True


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    done = 0
    for slug, source in slugs_and_sources():
        if fetch_one(slug, source):
            done += 1
    # Resize everything to 500px max edge
    for jpg in OUT.glob("*.jpg"):
        subprocess.run(
            ["sips", "-Z", "500", "-s", "formatOptions", "78", str(jpg)],
            capture_output=True,
        )
    print(f"wrote {done}/78 card images into {OUT}")
    return 0 if done == 78 else 1


if __name__ == "__main__":
    sys.exit(main())
