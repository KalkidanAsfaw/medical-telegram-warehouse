"""Task 5 - validate the Dagster pipeline definition (no execution)."""
import pytest

dagster = pytest.importorskip("dagster")

from pipeline import daily_schedule, defs  # noqa: E402

EXPECTED_OPS = {
    "scrape_telegram_data",
    "load_raw_to_postgres",
    "run_dbt_transformations",
    "run_yolo_enrichment",
}


def test_job_has_required_ops():
    job = defs.get_job_def("medical_warehouse_job")
    op_names = {n.name for n in job.graph.node_defs}
    assert EXPECTED_OPS <= op_names


def test_dependency_order():
    job = defs.get_job_def("medical_warehouse_job")
    # Map: downstream op -> set of upstream ops feeding it.
    upstream = {}
    for node, deps in job.dependencies.items():
        ups = {d.node for d in deps.values()}
        upstream[str(node.alias)] = ups
    assert upstream["load_raw_to_postgres"] == {"scrape_telegram_data"}
    assert upstream["run_dbt_transformations"] == {"load_raw_to_postgres"}
    assert upstream["run_yolo_enrichment"] == {"run_dbt_transformations"}


def test_daily_schedule():
    assert daily_schedule.cron_schedule == "0 6 * * *"
    assert daily_schedule.job.name == "medical_warehouse_job"
