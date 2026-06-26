"""Task 5 - Dagster orchestration.

Run: dagster dev -f pipeline.py   (UI at http://localhost:3000)

Ops (to implement):
  scrape_telegram_data -> load_raw_to_postgres -> run_dbt_transformations -> run_yolo_enrichment

TODO: define ops/assets, the job graph, and a daily schedule.
"""
from __future__ import annotations

from dagster import job, op


@op
def scrape_telegram_data():
    raise NotImplementedError


@op
def load_raw_to_postgres(scrape_telegram_data):
    raise NotImplementedError


@op
def run_dbt_transformations(load_raw_to_postgres):
    raise NotImplementedError


@op
def run_yolo_enrichment(run_dbt_transformations):
    raise NotImplementedError


@job
def medical_warehouse_pipeline():
    run_yolo_enrichment(run_dbt_transformations(load_raw_to_postgres(scrape_telegram_data())))
