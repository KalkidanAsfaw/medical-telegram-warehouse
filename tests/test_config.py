"""Smoke test so CI has something green until real tests land."""
from src.config import database_url


def test_database_url_builds():
    url = database_url()
    assert url.startswith("postgresql+psycopg2://")
