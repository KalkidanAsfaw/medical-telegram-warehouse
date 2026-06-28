"""Task 1 - Telegram scraper.

Extracts messages and images from public Telegram channels into the raw
data lake, preserving the original API structure:

    data/raw/telegram_messages/YYYY-MM-DD/<channel>.json
    data/raw/images/<channel>/<message_id>.jpg

Usage:
    python -m src.scraper                      # all channels from .env
    python -m src.scraper --channels CheMed123 # specific channel(s)
    python -m src.scraper --limit 200          # cap messages per channel
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Message, MessageMediaPhoto

from src import config
from src.logging_config import get_logger

logger = get_logger("scraper")

SESSION_PATH = config.PROJECT_ROOT / "telegram"


def _serialize_message(msg: Message, channel: str, image_path: str | None) -> dict:
    """Flatten a Telethon Message into the raw schema we persist."""
    return {
        "message_id": msg.id,
        "channel_name": channel,
        "message_date": msg.date.isoformat() if msg.date else None,
        "message_text": msg.message or "",
        "has_media": msg.media is not None,
        "image_path": image_path,
        "views": msg.views,
        "forwards": msg.forwards,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


async def _scrape_channel(
    client: TelegramClient, channel: str, limit: int | None
) -> int:
    """Scrape one channel; returns number of messages collected."""
    logger.info("Scraping channel: %s (limit=%s)", channel, limit)
    image_dir = config.RAW_IMAGES_DIR / channel
    image_dir.mkdir(parents=True, exist_ok=True)

    # Group messages by their date so each date partition gets its own file.
    by_date: dict[str, list[dict]] = defaultdict(list)
    count = 0

    try:
        async for msg in client.iter_messages(channel, limit=limit):
            image_path: str | None = None
            if isinstance(msg.media, MessageMediaPhoto):
                dest = image_dir / f"{msg.id}.jpg"
                try:
                    await client.download_media(msg, file=str(dest))
                    image_path = str(dest.relative_to(config.PROJECT_ROOT))
                except FloodWaitError as e:
                    logger.warning("Flood wait %ss downloading %s/%s", e.seconds, channel, msg.id)
                    await asyncio.sleep(e.seconds)
                except Exception:  # noqa: BLE001 - keep scraping despite a bad image
                    logger.exception("Failed to download image %s/%s", channel, msg.id)

            date_key = msg.date.strftime("%Y-%m-%d") if msg.date else "unknown"
            by_date[date_key].append(_serialize_message(msg, channel, image_path))
            count += 1

    except FloodWaitError as e:
        logger.warning("Flood wait %ss on channel %s; sleeping", e.seconds, channel)
        await asyncio.sleep(e.seconds)
    except Exception:  # noqa: BLE001
        logger.exception("Error while scraping channel %s", channel)

    for date_key, messages in by_date.items():
        out_dir = config.RAW_MESSAGES_DIR / date_key
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{channel}.json"
        with out_file.open("w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        logger.info("Wrote %d messages -> %s", len(messages), out_file)

    logger.info("Finished channel %s: %d messages", channel, count)
    return count


async def scrape(channels: list[str], limit: int | None) -> None:
    if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH:
        raise SystemExit(
            "Missing TELEGRAM_API_ID / TELEGRAM_API_HASH. Copy .env.example to .env "
            "and fill in your credentials from https://my.telegram.org."
        )
    if not channels:
        raise SystemExit("No channels to scrape. Set TELEGRAM_CHANNELS in .env or pass --channels.")

    config.RAW_MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
    config.RAW_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(SESSION_PATH), int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)
    await client.start(phone=config.TELEGRAM_PHONE)
    logger.info("Authenticated. Scraping %d channel(s).", len(channels))

    total = 0
    try:
        for channel in channels:
            total += await _scrape_channel(client, channel, limit)
    finally:
        await client.disconnect()
    logger.info("Done. %d messages across %d channel(s).", total, len(channels))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape Telegram channels into the raw data lake.")
    p.add_argument("--channels", nargs="*", default=config.TELEGRAM_CHANNELS,
                   help="Channel usernames (default: TELEGRAM_CHANNELS from .env).")
    p.add_argument("--limit", type=int, default=None,
                   help="Max messages per channel (default: all).")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(scrape(args.channels, args.limit))


if __name__ == "__main__":
    main()
