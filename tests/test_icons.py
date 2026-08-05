"""Verifies that every card has a corresponding icon file, the icons are valid SVG,
and they use currentColor so the card's accent drives their appearance.
"""

from __future__ import annotations

import pathlib
import re
import xml.etree.ElementTree as ET

import pytest

from app.data.loader import load_deck
from app.static.icons._generate import iter_card_names

ICONS_DIR = pathlib.Path(__file__).parent.parent / "app" / "static" / "icons"
SVG_NS = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("slug,body", list(iter_card_names()))
def test_icon_file_is_valid_svg(slug: str, body: str) -> None:
    """Each generated icon must parse as well-formed SVG and use currentColor."""
    path = ICONS_DIR / f"{slug}.svg"
    assert path.exists(), f"missing icon: {path}"
    content = path.read_text(encoding="utf-8")
    assert content.startswith("<svg"), f"{slug}: missing <svg> root"

    # XML parses cleanly (we strip the <title> check via namespace handling).
    ET.fromstring(content)

    # currentColor must be present so the card's accent drives the colour.
    assert "currentColor" in content, f"{slug}: does not use currentColor"


def test_every_deck_card_has_an_icon() -> None:
    """Cards in the deck must have a matching icon file."""
    deck = load_deck()
    missing = [c.slug for c in deck.cards if not (ICONS_DIR / f"{c.slug}.svg").exists()]
    assert not missing, f"missing icons: {missing}"


def test_icon_sizes_are_reasonable() -> None:
    """Each icon should stay under 2KB so the whole deck fits in <200KB."""
    for path in ICONS_DIR.glob("*.svg"):
        size = path.stat().st_size
        assert size < 2048, f"{path.name} is {size}b, expected <2048b"


def test_deal_html_references_card_icons() -> None:
    """The deal partial must reference the icon for every dealt card."""
    from datetime import date
    from fastapi.testclient import TestClient
    from app import config
    from app.main import create_app
    import os, tempfile

    with tempfile.TemporaryDirectory() as td:
        os.environ["SYZYGY_DB"] = f"{td}/t.db"
        os.environ["SYZYGY_SECRET"] = "x"
        config.get_settings.cache_clear()
        try:
            client = TestClient(create_app())
            response = client.post(
                "/readings/",
                data={"name": "Ada", "age": "29", "resonance": "Female", "spread_slug": "single", "save": "on"},
            )
            assert response.status_code == 200
            refs = re.findall(r"/static/icons/([a-z0-9-]+)\.svg", response.text)
            assert len(refs) >= 3, f"expected corner+watermark refs, got {refs}"
        finally:
            config.get_settings.cache_clear()
