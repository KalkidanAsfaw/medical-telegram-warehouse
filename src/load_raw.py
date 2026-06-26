"""Task 2 (load step) - load raw JSON from the data lake into PostgreSQL.

Reads every data/raw/telegram_messages/YYYY-MM-DD/<channel>.json file and
loads the records into ``raw.telegram_messages`` with all scraped fields
preserved. The load is idempotent: re-running upserts on
(channel_name, message_id) so it is safe to run repeatedly (e.g. from
Dagster on a schedule).

Usage:
    python -m src.load_raw                 # load everything in the data lake
    python -m src.load_raw --truncate      # wipe the table first, then load
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from src import config
from src.logging_config import get_logger

logger = get_logger("load_raw")

RAW_SCHEMA = config.POSTGRES_RAW_SCHEMA
RAW_TABLE = f"{RAW_SCHEMA}.telegram_messages"

# Order matters: must match the VALUES tuple built in _to_row().
COLUMNS = [
    "message_id",
    "channel_name",
    "message_date",
    "message_text",
    "has_media",
    "image_path",
    "views",
    "forwards",
    "scraped_at",
    "source_file",
]

DDL = f"""
CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA};

CREATE TABLE IF NOT EXISTS {RAW_TABLE} (
    message_id   BIGINT       NOT NULL,
    channel_name TEXT         NOT NULL,
    message_date TIMESTAMPTZ,
    message_text TEXT,
    has_media    BOOLEAN,
    image_path   TEXT,
    views        INTEGER,
    forwards     INTEGER,
    scraped_at   TIMESTAMPTZ,
    source_file  TEXT,
    loaded_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (channel_name, message_id)
);
"""

UPSERT = f"""
INSERT INTO {RAW_TABLE} ({", ".join(COLUMNS)})
VALUES %s
ON CONFLICT (channel_name, message_id) DO UPDATE SET
    message_date = EXCLUDED.message_date,
    message_text = EXCLUDED.message_text,
    has_media    = EXCLUDED.has_media,
    image_path   = EXCLUDED.image_path,
    views        = EXCLUDED.views,
    forwards     = EXCLUDED.forwards,
    scraped_at   = EXCLUDED.scraped_at,
    source_file  = EXCLUDED.source_file,
    loaded_at    = now();
"""


def _connect():
    return psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )


def _to_row(rec: dict, source_file: str) -> tuple:
    return (
        rec.get("message_id"),
        rec.get("channel_name"),
        rec.get("message_date"),
        rec.get("message_text"),
        rec.get("has_media"),
        rec.get("image_path"),
        rec.get("views"),
        rec.get("forwards"),
        rec.get("scraped_at"),
        source_file,
    )


def _iter_records():
    """Yield (row_tuple) for every record across all data-lake JSON files."""
    files = sorted(config.RAW_MESSAGES_DIR.glob("*/*.json"))
    if not files:
        logger.warning("No JSON files found under %s", config.RAW_MESSAGES_DIR)
    for path in files:
        rel = str(path.relative_to(config.PROJECT_ROOT))
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.exception("Skipping malformed JSON: %s", rel)
            continue
        logger.info("Reading %d records from %s", len(records), rel)
        for rec in records:
            yield _to_row(rec, rel)


def load(truncate: bool = False) -> int:
    rows = list(_iter_records())
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(DDL)
            if truncate:
                logger.info("Truncating %s", RAW_TABLE)
                cur.execute(f"TRUNCATE {RAW_TABLE};")
            if rows:
                execute_values(cur, UPSERT, rows, page_size=500)
            cur.execute(f"SELECT count(*) FROM {RAW_TABLE};")
            total = cur.fetchone()[0]
    finally:
        conn.close()
    logger.info("Loaded %d records; %s now holds %d rows.", len(rows), RAW_TABLE, total)
    return total


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load raw Telegram JSON into PostgreSQL.")
    p.add_argument("--truncate", action="store_true", help="Empty the table before loading.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    load(truncate=args.truncate)


if __name__ == "__main__":
    main()
