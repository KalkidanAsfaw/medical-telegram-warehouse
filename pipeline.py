"""Task 5 - Dagster orchestration.

Wires the whole ELT pipeline into a single observable, schedulable job:

    scrape_telegram_data
        -> load_raw_to_postgres
            -> run_dbt_transformations
                -> run_yolo_enrichment

Run the UI:   dagster dev -f pipeline.py      (http://localhost:3000)
Run headless: dagster job execute -f pipeline.py -j medical_warehouse_job
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from dagster import (
    Definitions,
    RetryPolicy,
    ScheduleDefinition,
    job,
    op,
)

PROJECT_ROOT = Path(__file__).resolve().parent
DBT_DIR = PROJECT_ROOT / "medical_warehouse"

# Retry transient failures (e.g. Telegram rate limits, flaky network).
DEFAULT_RETRY = RetryPolicy(max_retries=2, delay=30)


@op(retry_policy=DEFAULT_RETRY)
def scrape_telegram_data(context) -> int:
    """Task 1 - scrape configured Telegram channels into the raw data lake."""
    import asyncio

    from src import config
    from src.scraper import scrape

    channels = config.TELEGRAM_CHANNELS
    context.log.info("Scraping channels: %s", channels)
    asyncio.run(scrape(channels, limit=None))
    return len(channels)


@op
def load_raw_to_postgres(context, scraped_channels: int) -> int:
    """Task 2 (load) - load the data lake JSON into raw.telegram_messages."""
    from src.load_raw import load

    total = load()
    context.log.info("raw.telegram_messages now holds %d rows (from %d channels).",
                     total, scraped_channels)
    return total


@op
def run_dbt_transformations(context, raw_rows: int) -> str:
    """Task 2 (transform) - build and test the dbt star schema."""
    context.log.info("Running dbt build on %d raw rows.", raw_rows)
    result = subprocess.run(
        ["dbt", "build", "--profiles-dir", "."],
        cwd=str(DBT_DIR), capture_output=True, text=True,
    )
    context.log.info(result.stdout[-2000:])
    if result.returncode != 0:
        context.log.error(result.stderr[-2000:])
        raise RuntimeError("dbt build failed")
    return "dbt build complete"


@op
def run_yolo_enrichment(context, dbt_status: str) -> int:
    """Task 3 - run YOLO detection, load results, and build the image-detection model."""
    from src.load_detections import load as load_detections
    from src.yolo_detect import DEFAULT_CONF, DEFAULT_MODEL, detect

    context.log.info("Upstream: %s. Running YOLO detection.", dbt_status)
    detect(DEFAULT_MODEL, DEFAULT_CONF, limit=None)
    rows = load_detections()

    # Build the image-detection dbt models now that raw.image_detections is loaded.
    result = subprocess.run(
        ["dbt", "build", "--select", "stg_image_detections+", "--profiles-dir", "."],
        cwd=str(DBT_DIR), capture_output=True, text=True,
    )
    context.log.info(result.stdout[-2000:])
    if result.returncode != 0:
        context.log.error(result.stderr[-2000:])
        raise RuntimeError("dbt build of image-detection models failed")
    return rows


@job
def medical_warehouse_job():
    """Full ELT pipeline graph with explicit op dependencies."""
    run_yolo_enrichment(
        run_dbt_transformations(
            load_raw_to_postgres(
                scrape_telegram_data()
            )
        )
    )


# Run the pipeline once per day at 06:00.
daily_schedule = ScheduleDefinition(
    job=medical_warehouse_job,
    cron_schedule="0 6 * * *",
    name="daily_medical_warehouse_schedule",
)

defs = Definitions(
    jobs=[medical_warehouse_job],
    schedules=[daily_schedule],
)
