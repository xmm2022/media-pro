# GD Source-First Playback Gateway

## MVP Route Order

The playback decision order is `self -> pool -> source_copy -> source_stream`.

## Local Development

```bash
cp .env.example .env
uv sync
uv run uvicorn gateway.main:app --reload
```

## Validation

```bash
uv run python scripts/validate_openlist_stream.py
uv run python scripts/validate_rapid_copy.py
uv run python scripts/verify_mvp.py
```
