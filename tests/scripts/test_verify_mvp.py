from ast import literal_eval
import subprocess
import sys
from pathlib import Path


def test_readme_mentions_mvp_route_order() -> None:
    readme = Path("/root/gd-playback-gateway/README.md").read_text()

    assert "self -> pool -> source_copy -> source_stream" in readme
    assert "uv run python scripts/verify_mvp.py" in readme


def test_verify_mvp_script_runs_and_reports_expected_output() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "verify_mvp.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    output = literal_eval(result.stdout.strip())

    assert output == {
        "health": 200,
        "playback_route": "source_copy",
        "stats_keys": ["pool", "self", "source_copy", "source_stream"],
    }
