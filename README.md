# Medical Telegram Warehouse

An end-to-end ELT data platform that turns raw Telegram data from Ethiopian
medical/pharmaceutical channels into an analytical API.

**Stack:** Telethon (scrape) → Data Lake (JSON + images) → PostgreSQL (raw) →
dbt (star schema) → YOLOv8 (image enrichment) → FastAPI (analytics) → Dagster
(orchestration). Containerized with Docker.

> 10 Academy KAIM — Week 8 Challenge (24–30 Jun 2026).

---

## Architecture

```
Telegram ──Telethon──► Data Lake ──load_raw──► PostgreSQL ──dbt──► Star Schema ──► FastAPI
(channels)            (JSON+imgs)   (raw schema)            (staging→marts)        (/docs)
                                          ▲                       ▲
                                          └──── YOLOv8 image enrichment ────┘
                              All steps orchestrated & scheduled by Dagster
```

### Data lake layout
```
data/raw/telegram_messages/YYYY-MM-DD/<channel>.json   # raw messages, API shape preserved
data/raw/images/<channel>/<message_id>.jpg             # downloaded photos
```

### Star schema (Task 2)
- **fct_messages** — message_id, channel_key (FK), date_key (FK), message_text,
  message_length, views, forwards, has_image
- **dim_channels** — channel_key (surrogate), channel_name, channel_type,
  first/last_post_date, total_posts, avg_views
- **dim_dates** — date_key, full_date, day_of_week, day_name, week_of_year,
  month, month_name, quarter, year, is_weekend
- **fct_image_detections** (Task 3) — message_id, channel_key, date_key,
  detected_class, confidence_score, image_category

---

## Project layout
```
medical-telegram-warehouse/
├── docker-compose.yml / Dockerfile / requirements.txt
├── .env.example                 # copy to .env and fill in secrets
├── pipeline.py                  # Dagster job (Task 5)
├── src/
│   ├── config.py                # env-driven settings + DB URL
│   ├── scraper.py               # Task 1: Telethon scraper
│   ├── load_raw.py              # Task 2: JSON -> raw.telegram_messages
│   ├── yolo_detect.py           # Task 3: YOLOv8 detection + classification
│   └── api/                     # Task 4: FastAPI (main / database / schemas)
├── medical_warehouse/           # dbt project (Task 2)
│   ├── dbt_project.yml / profiles.yml
│   └── models/{staging,marts}/  + tests/
├── data/raw/{telegram_messages,images}/   # data lake (gitignored)
├── logs/  notebooks/  scripts/  tests/
└── .github/workflows/unittests.yml
```

---

## Setup
```bash
cp .env.example .env          # fill in Telegram + Postgres creds
docker compose up -d postgres # start the warehouse
pip install -r requirements.txt
```

---

## Implementation plan & status

| Task | Deliverable | Key files | Status |
|------|-------------|-----------|--------|
| 0 | Env, Docker, repo scaffold | `Dockerfile`, `docker-compose.yml`, `.gitignore` | ✅ done |
| 1 | Telegram scraper → data lake | `src/scraper.py`, `data/raw/...` | ⬜ todo |
| 2 | Load to Postgres + dbt star schema + tests | `src/load_raw.py`, `medical_warehouse/` | ⬜ todo |
| 3 | YOLOv8 enrichment + `fct_image_detections` | `src/yolo_detect.py` | ⬜ todo |
| 4 | FastAPI analytical endpoints | `src/api/` | ⬜ todo |
| 5 | Dagster orchestration + schedule | `pipeline.py` | ⬜ todo |

### Task details
1. **Scrape (Telethon):** auth via `.env`; for each channel pull message_id,
   date, text, views, forwards, media; download photos; write partitioned JSON;
   log activity/errors to `logs/`.
2. **Transform (dbt):** `load_raw.py` lands JSON into `raw.telegram_messages`;
   `stg_telegram_messages` casts types, renames, filters empties, adds
   message_length/has_image; build `dim_channels`, `dim_dates`, `fct_messages`;
   add `unique`/`not_null`/`relationships` tests + custom tests
   (`assert_no_future_messages`, `assert_positive_views`); `dbt docs generate`.
3. **Enrich (YOLO):** run `yolov8n.pt` over images, record class+confidence,
   classify (promotional/product_display/lifestyle/other), load into
   `fct_image_detections` joined on message_id.
4. **API (FastAPI):** `/api/reports/top-products`, `/api/channels/{name}/activity`,
   `/api/search/messages`, `/api/reports/visual-content`; Pydantic schemas; `/docs`.
5. **Orchestrate (Dagster):** ops scrape → load → dbt → yolo with deps; daily
   schedule + failure alerts; UI at `:3000`.

---

## Key dates
- **Interim** (Tasks 1–2): Sun 28 Jun 2026, 20:00 UTC
- **Final** (all tasks + report): Tue 30 Jun 2026, 20:00 UTC
