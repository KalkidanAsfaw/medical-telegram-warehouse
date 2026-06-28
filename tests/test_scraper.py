"""Validate the raw record structure produced by the Task 1 scraper.

These tests run without live Telegram access: they exercise the pure
serializer against a fake message, and assert the on-disk contract that
the Task 2 loader / dbt staging models depend on.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import config
from src.scraper import _serialize_message

# The exact schema downstream (load_raw + stg_telegram_messages) relies on.
EXPECTED_KEYS = {
    "message_id",
    "channel_name",
    "message_date",
    "message_text",
    "has_media",
    "image_path",
    "views",
    "forwards",
    "scraped_at",
}


def _fake_message(*, media=None, text="hello", date=None):
    return SimpleNamespace(
        id=42,
        date=date or datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc),
        message=text,
        media=media,
        views=100,
        forwards=5,
    )


def test_serialize_has_exactly_expected_keys():
    rec = _serialize_message(_fake_message(), "CheMed123", None)
    assert set(rec.keys()) == EXPECTED_KEYS


def test_serialize_field_types():
    rec = _serialize_message(_fake_message(), "CheMed123", None)
    assert isinstance(rec["message_id"], int)
    assert rec["channel_name"] == "CheMed123"
    assert isinstance(rec["message_text"], str)
    assert isinstance(rec["has_media"], bool)
    assert isinstance(rec["views"], int)
    assert isinstance(rec["forwards"], int)
    # message_date must be an ISO-8601 string the warehouse can cast.
    datetime.fromisoformat(rec["message_date"])
    datetime.fromisoformat(rec["scraped_at"])


def test_media_flags_consistent_when_image_present():
    rec = _serialize_message(
        _fake_message(media=object()), "CheMed123", "data/raw/images/CheMed123/42.jpg"
    )
    assert rec["has_media"] is True
    assert rec["image_path"].endswith("42.jpg")


def test_no_media_has_null_image_path():
    rec = _serialize_message(_fake_message(media=None), "CheMed123", None)
    assert rec["has_media"] is False
    assert rec["image_path"] is None


def test_empty_text_becomes_empty_string():
    rec = _serialize_message(_fake_message(text=None), "CheMed123", None)
    assert rec["message_text"] == ""


# --- Contract check against any real scraped output (skips if none exists) ---

def _scraped_files() -> list[Path]:
    if not config.RAW_MESSAGES_DIR.exists():
        return []
    return sorted(config.RAW_MESSAGES_DIR.glob("*/*.json"))


@pytest.mark.parametrize("path", _scraped_files() or [pytest.param(None, marks=pytest.mark.skip(reason="no scraped data present"))])
def test_on_disk_records_match_schema(path):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    assert isinstance(records, list) and records, f"{path} should hold a non-empty list"
    for rec in records:
        assert set(rec.keys()) == EXPECTED_KEYS, f"bad keys in {path}"
        assert isinstance(rec["message_id"], int)
        if rec["has_media"] is False:
            assert rec["image_path"] is None
