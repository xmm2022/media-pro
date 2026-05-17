from pathlib import Path


def test_readme_mentions_mvp_route_order() -> None:
    readme = Path("/root/gd-playback-gateway/README.md").read_text()

    assert "self -> pool -> source_copy -> source_stream" in readme
    assert "uv run python scripts/verify_mvp.py" in readme
