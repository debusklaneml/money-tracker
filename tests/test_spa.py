"""Tests for Phase 5 single-process SPA serving (bead bud-n3z).

These assert the FastAPI app serves the built React SPA from the same port as
the API: real assets resolve, client-side deep links fall back to index.html,
and unknown ``/api/*`` paths still 404 as JSON rather than the HTML shell.

The whole module is skipped unless ``frontend/dist`` exists, so it is a no-op
until ``npm run build`` has run (matching the ``is_dir()`` guard in main.py).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app

_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

pytestmark = pytest.mark.skipif(
    not _DIST.is_dir(), reason="frontend/dist not built (run `npm run build`)"
)

client = TestClient(app)


def test_root_serves_spa_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "<div id=\"root\">" in r.text or "<div id='root'>" in r.text


def test_deep_link_falls_back_to_index():
    """A hard refresh on a client-side route must return the HTML shell."""
    r = client.get("/transactions")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_health_still_wins_over_spa():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_unknown_api_path_404s_as_json_not_html():
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert "text/html" not in r.headers.get("content-type", "")


def test_hashed_assets_are_served():
    assets = _DIST / "assets"
    asset = next((p for p in assets.iterdir() if p.is_file()), None)
    assert asset is not None, "build produced no assets"
    r = client.get(f"/assets/{asset.name}")
    assert r.status_code == 200
