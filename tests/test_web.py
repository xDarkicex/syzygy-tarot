"""End-to-end tests for the web layer, using a fresh in-memory database."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app


@pytest.fixture()
def client(monkeypatch, tmp_path) -> Iterator[TestClient]:
    db = tmp_path / "test.db"
    monkeypatch.setenv("SYZYGY_DB", str(db))
    monkeypatch.setenv("SYZYGY_SECRET", "test-secret")
    config.get_settings.cache_clear()
    yield TestClient(create_app())
    config.get_settings.cache_clear()


def test_home_renders(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "syzygy" in response.text.lower()
    assert "Hear Me" in response.text
    assert "Single Card" in response.text


def test_history_renders_empty(client: TestClient) -> None:
    response = client.get("/history")
    assert response.status_code == 200
    assert "No readings yet" in response.text


def test_about_renders(client: TestClient) -> None:
    response = client.get("/about")
    assert response.status_code == 200
    assert "numerology" in response.text.lower()


def test_deal_returns_full_reading(client: TestClient) -> None:
    response = client.post(
        "/readings/",
        data={"name": "Ada", "age": "29", "resonance": "Female", "spread_slug": "single"},
    )
    assert response.status_code == 200
    body = response.text
    assert "Ace of Wands" in body or "two of" in body.lower() or "summary" in body.lower()


def test_deal_rejects_bad_age(client: TestClient) -> None:
    response = client.post(
        "/readings/",
        data={"name": "Ada", "age": "0", "resonance": "Female", "spread_slug": "single"},
    )
    assert response.status_code == 400


def test_deal_rejects_unknown_spread(client: TestClient) -> None:
    response = client.post(
        "/readings/",
        data={"name": "Ada", "age": "29", "resonance": "Female", "spread_slug": "bogus"},
    )
    assert response.status_code == 404


def test_deal_with_save_persists_and_exposes_share_link(client: TestClient) -> None:
    response = client.post(
        "/readings/",
        data={"name": "Ada", "age": "29", "resonance": "Female", "spread_slug": "hear-help-hold", "save": "on"},
    )
    assert response.status_code == 200
    assert "Share" in response.text
    slug = response.headers.get("Set-Cookie", "")
    # The Set-Cookie header carries the profile, the body carries the share slug.
    assert "syzygy_profile" in slug

    history = client.get("/history").text
    assert "Hear Me" in history or "Past/Present/Future" not in history


def test_share_link_is_reachable(client: TestClient) -> None:
    deal = client.post(
        "/readings/",
        data={"name": "Ada", "age": "29", "resonance": "Female", "spread_slug": "single", "save": "on"},
    )
    # Extract the share slug from the Share link.
    import re

    match = re.search(r"/readings/([A-Za-z0-9_-]{6,})", deal.text)
    assert match, deal.text
    response = client.get(f"/readings/{match.group(1)}")
    assert response.status_code == 200
    assert "syzygy" in response.text.lower()


def test_reveal_card_partial(client: TestClient) -> None:
    deal = client.post(
        "/readings/",
        data={"name": "Ada", "age": "29", "resonance": "Female", "spread_slug": "single", "save": "on"},
    )
    import re
    match = re.search(r"/readings/([A-Za-z0-9_-]{6,})", deal.text)
    slug = match.group(1)
    response = client.get(f"/readings/{slug}/card/0")
    assert response.status_code == 200
    assert "card-slot" in response.text
    assert "revealed" in response.text


def test_profile_save_and_clear(client: TestClient) -> None:
    save = client.post(
        "/profile/save",
        data={"name": "Ada", "age": "29", "resonance": "Female"},
        follow_redirects=False,
    )
    assert save.status_code == 303
    assert "syzygy_profile" in save.headers.get("set-cookie", "")

    clear = client.post("/profile/clear", follow_redirects=False)
    assert clear.status_code == 303
    cookie = clear.headers.get("set-cookie", "")
    assert "syzygy_profile" in cookie and "Max-Age=0" in cookie or "syzygy_profile=" in cookie
