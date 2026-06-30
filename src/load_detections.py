"""Task 3 (load step) - load YOLO detection results into PostgreSQL.

Reads data/processed/image_detections.csv (produced by src/yolo_detect.py)
and loads it into raw.image_detections, ready for the dbt
fct_image_detections model to join against fct_messages.

Usage:
    python -m src.load_detections
"""
from __future__ import annotations

import csv

import psycopg2
from psycopg2.extras import execute_values

from src import config
from src.logging_config import get_logger

logger = get_logger("load_detections")

RAW_SCHEMA = config.POSTGRES_RAW_SCHEMA
RAW_TABLE = f"{RAW_SCHEMA}.image_detections"
INPUT_CSV = config.DATA_DIR / "processed" / "image_detections.csv"

DDL = f"""
CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA};
DROP TABLE IF EXISTS {RAW_TABLE};
CREATE TABLE {RAW_TABLE} (
    message_id       BIGINT,
    channel_name     TEXT,
    image_path       TEXT,
    detected_class   TEXT,
    confidence_score NUMERIC,
    image_category   TEXT,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

INSERT = f"""
INSERT INTO {RAW_TABLE}
    (message_id, channel_name, image_path, detected_class, confidence_score, image_category)
VALUES %s;
"""


def _connect():
    return psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )


def _rows():
    if not INPUT_CSV.exists():
        raise SystemExit(f"Detections CSV not found: {INPUT_CSV}. Run src.yolo_detect first.")
    with INPUT_CSV.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            yield (
                int(r["message_id"]) if r["message_id"] else None,
                r["channel_name"] or None,
                r["image_path"] or None,
                r["detected_class"] or None,
                float(r["confidence_score"]) if r["confidence_score"] else None,
                r["image_category"] or None,
            )


def load() -> int:
    rows = list(_rows())
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(DDL)
            if rows:
                execute_values(cur, INSERT, rows, page_size=500)
            cur.execute(f"SELECT count(*) FROM {RAW_TABLE};")
            total = cur.fetchone()[0]
    finally:
        conn.close()
    logger.info("Loaded %d rows; %s now holds %d rows.", len(rows), RAW_TABLE, total)
    return total


def main() -> None:
    load()


if __name__ == "__main__":
    main()
