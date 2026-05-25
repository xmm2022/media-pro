from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.main import create_app
from gateway.models import Base

DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def _client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'spa.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return TestClient(create_app(database_url=database_url))


def test_admin_root_serves_index_html(tmp_path: Path) -> None:
    assert (DIST / "index.html").exists(), "web/dist/index.html missing — run `pnpm build` first"
    with _client(tmp_path) as client:
        response = client.get("/admin")

    assert response.status_code == 200
    assert "<div id=\"app\"></div>" in response.text


def test_admin_subroute_falls_through_to_index_html(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/admin/login")

    assert response.status_code == 200
    assert "<div id=\"app\"></div>" in response.text


def test_admin_assets_directory_is_mounted(tmp_path: Path) -> None:
    assets_dir = DIST / "assets"
    asset_files = list(assets_dir.iterdir())
    assert asset_files, "web/dist/assets is empty — rebuild the frontend"
    asset = next(p for p in asset_files if p.is_file())
    with _client(tmp_path) as client:
        response = client.get(f"/admin/assets/{asset.name}")
    assert response.status_code == 200
