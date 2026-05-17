import subprocess
from pathlib import Path
from ast import literal_eval


def test_readme_mentions_mvp_route_order() -> None:
    readme = Path("/root/gd-playback-gateway/README.md").read_text()

    assert "self -> pool -> source_copy -> source_stream" in readme
    assert "uv run python scripts/verify_mvp.py" in readme


def test_verify_mvp_script_runs_and_reports_expected_output() -> None:
    result = subprocess.run(
        [
            "/root/.local/bin/uv",
            "run",
            "python",
            "scripts/verify_mvp.py",
        ],
        cwd="/root/gd-playback-gateway",
        check=True,
        capture_output=True,
        text=True,
    )

    output = literal_eval(result.stdout.strip())

    assert output == {
        "health": 200,
        "playback_route": "source_stream",
        "stats_keys": ["pool", "self", "source_copy", "source_stream"],
    }
