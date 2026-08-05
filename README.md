# syzygy-tarot

A modern web revisioning of [xDarkicex/tarot](https://github.com/xDarkicex/tarot) — the
original was a Java console tarot reader. This is a FastAPI + htmx + Alpine.js web app.

## What carries over

- The full 78-card deck and its interpretive voice.
- The **numerology seed**: your name, age, and the day of the year determine your shuffle,
  so the same person gets the same reading all day.
- The signature three-card spread: **Hear Me / Help Me / Hold Me**.

## What's new

- Reversed meanings for all 78 cards. The original had a `anti` field on every card that was
  never filled in, so reversed draws rendered blank.
- A web GUI with card-flip reveals.
- Profiles kept in localStorage and a cookie, so there's no signup or auth.
- Readings persisted to SQLite with shareable permalinks.
- Additional spreads alongside the signature one.

## Stack

FastAPI, Jinja2, htmx, Alpine.js, SQLite.

## Development

```sh
uv venv
uv pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Run the checks:

```sh
pytest
ruff check .
```

### Complexity budget

Every function must stay under a cyclomatic complexity of 10, with thin route handlers that
delegate to services. This is enforced by `ruff` via `max-complexity = 9` in `pyproject.toml`,
so `ruff check .` fails the build rather than relying on discipline.
