"""Task 4 - API endpoint tests.

These hit the live warehouse via TestClient. If the database/marts are not
reachable (e.g. plain CI without Postgres), the whole module is skipped.
"""
import pytest
from fastapi.testclient import TestClient

from src.api.database import engine
from src.api.main import app


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("select 1 from public_marts.fct_messages limit 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="warehouse marts not reachable")

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_top_products_shape_and_limit():
    r = client.get("/api/reports/top-products?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert len(data) <= 5
    if data:
        assert {"term", "mentions"} == set(data[0].keys())
        # results are sorted by mentions desc
        assert data == sorted(data, key=lambda d: d["mentions"], reverse=True)


def test_channel_activity_ok_and_404():
    ok = client.get("/api/channels/tikvahpharma/activity")
    assert ok.status_code == 200
    body = ok.json()
    assert body["channel_name"] == "tikvahpharma"
    assert isinstance(body["daily_activity"], list)
    assert client.get("/api/channels/does-not-exist/activity").status_code == 404


def test_search_messages():
    r = client.get("/api/search/messages?query=pharma&limit=3")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "pharma"
    assert body["count"] == len(body["results"]) <= 3


def test_search_requires_query():
    # min_length=2 -> 422 validation error when too short
    assert client.get("/api/search/messages?query=a").status_code == 422


def test_visual_content():
    r = client.get("/api/reports/visual-content")
    assert r.status_code == 200
    data = r.json()
    assert data
    row = data[0]
    assert {"channel_name", "channel_type", "total_posts", "posts_with_image",
            "image_share_pct", "promotional", "product_display", "lifestyle",
            "other"} <= set(row.keys())
    assert 0 <= row["image_share_pct"] <= 100
