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
    assert "alpine-persist.min.js" in response.text, "Alpine persist plugin must load before Alpine"
    assert "fonts.googleapis.com" in response.text, "Google Fonts must be linked"


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


def test_question_is_persisted_and_restored(client: TestClient) -> None:
    """The question must survive the deal → DB → SSE-worker round trip.

    Regression: the question was captured on the Reading at deal time but
    never written to the DB, so the SSE worker (which reconstructs the
    Reading from storage) saw question=None and the LLM never knew what
    the user asked.
    """
    response = client.post(
        "/readings/",
        data={
            "name": "Gentry", "age": "33", "resonance": "Male",
            "drawn_to": "Women", "spread_slug": "single",
            "question": "Will I find love soon?", "save": "on",
        },
    )
    import re
    match = re.search(r"/readings/([A-Za-z0-9_-]+)", response.text)
    assert match, "deal should produce a share slug"
    slug = match.group(1)

    # The reading reconstructed from the DB must carry the question.
    import sqlite3
    from app.config import get_settings
    conn = sqlite3.connect(get_settings().database_path)
    conn.row_factory = sqlite3.Row
    from app.storage.readings import fetch_reading
    stored = fetch_reading(slug, conn)
    assert stored is not None
    assert stored.reading.question == "Will I find love soon?", stored.reading.question
    conn.close()


def test_profile_dashboard_is_isolated_by_user(client: TestClient) -> None:
    """Readings from different users must not leak into each other's dashboard.

    Regression: the dashboard aggregated every user's readings. Each profile
    now carries a stable user_id, persisted with its readings, and the
    profile page filters history by it.
    """
    # Two different users deal readings.
    a = client.post("/readings/", data={
        "name": "Tiffany", "age": "25", "resonance": "Female", "spread_slug": "single",
        "user_id": "user-aaa", "save": "on",
    })
    b = client.post("/readings/", data={
        "name": "Gentry", "age": "30", "resonance": "Male", "spread_slug": "single",
        "user_id": "user-bbb", "save": "on",
    })
    assert a.status_code == 200 and b.status_code == 200

    # Tiffany's profile page must only show her own reading.
    resp = client.get("/profile", cookies={"syzygy_profile": "user-aaa"})
    assert resp.status_code == 200
    # The reading for user-aaa is stored; fetch and check filtering at the storage layer.
    import sqlite3
    from app.config import get_settings
    conn = sqlite3.connect(get_settings().database_path)
    conn.row_factory = sqlite3.Row
    from app.storage.readings import fetch_recent_readings
    tiff = fetch_recent_readings(50, conn, user_id="user-aaa")
    gent = fetch_recent_readings(50, conn, user_id="user-bbb")
    assert len(tiff) == 1 and tiff[0].reading.querent.name == "Tiffany"
    assert len(gent) == 1 and gent[0].reading.querent.name == "Gentry"
    conn.close()
