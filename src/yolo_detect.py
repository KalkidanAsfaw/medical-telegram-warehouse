"""Task 3 - YOLOv8 object detection over scraped images.

Scans data/raw/images/<channel>/<message_id>.jpg, runs YOLOv8n detection on
each image, records detected objects with confidence scores, derives an image
category, and writes the results to a CSV (one row per detected object; images
with no detections get a single 'other' row).

Image categories:
  promotional     - person AND a product/container present
  product_display - product/container present, no person
  lifestyle       - person present, no product
  other           - neither detected

Usage:
    python -m src.yolo_detect                  # all images, default model
    python -m src.yolo_detect --limit 100      # cap images (quick test)
    python -m src.yolo_detect --conf 0.35      # confidence threshold
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from src import config
from src.logging_config import get_logger

logger = get_logger("yolo_detect")

DEFAULT_MODEL = "yolov8n.pt"
DEFAULT_CONF = 0.25
OUTPUT_CSV = config.DATA_DIR / "processed" / "image_detections.csv"

# COCO classes we treat as a "product / container" for the classification scheme.
PRODUCT_CLASSES = {"bottle", "cup", "bowl", "vase", "wine glass", "jar"}
PERSON_CLASS = "person"

CSV_FIELDS = [
    "message_id",
    "channel_name",
    "image_path",
    "detected_class",
    "confidence_score",
    "image_category",
]


def _classify(classes: set[str]) -> str:
    has_person = PERSON_CLASS in classes
    has_product = bool(classes & PRODUCT_CLASSES)
    if has_person and has_product:
        return "promotional"
    if has_product:
        return "product_display"
    if has_person:
        return "lifestyle"
    return "other"


def _parse_message_id(path: Path) -> int | None:
    """Image files are named <message_id>.jpg."""
    m = re.match(r"(\d+)", path.stem)
    return int(m.group(1)) if m else None


def _iter_images(limit: int | None):
    files = sorted(config.RAW_IMAGES_DIR.glob("*/*.jpg"))
    if limit:
        files = files[:limit]
    return files


def detect(model_name: str, conf: float, limit: int | None) -> int:
    # Imported here so the module loads even before ultralytics is installed.
    from ultralytics import YOLO

    images = _iter_images(limit)
    if not images:
        logger.warning("No images found under %s", config.RAW_IMAGES_DIR)
        return 0

    logger.info("Loading model %s; running on %d images (conf=%.2f)", model_name, len(images), conf)
    model = YOLO(model_name)
    names = model.names  # class-id -> name

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        for path in images:
            channel = path.parent.name
            message_id = _parse_message_id(path)
            rel = str(path.relative_to(config.PROJECT_ROOT))
            try:
                result = model.predict(str(path), conf=conf, verbose=False)[0]
            except Exception:  # noqa: BLE001 - skip unreadable images, keep going
                logger.exception("Detection failed for %s", rel)
                continue

            detections = [
                (names[int(b.cls)], float(b.conf))
                for b in result.boxes
            ] if result.boxes is not None else []

            category = _classify({c for c, _ in detections})

            if detections:
                for cls_name, score in detections:
                    writer.writerow({
                        "message_id": message_id,
                        "channel_name": channel,
                        "image_path": rel,
                        "detected_class": cls_name,
                        "confidence_score": round(score, 4),
                        "image_category": category,
                    })
                    rows_written += 1
            else:
                writer.writerow({
                    "message_id": message_id,
                    "channel_name": channel,
                    "image_path": rel,
                    "detected_class": None,
                    "confidence_score": None,
                    "image_category": "other",
                })
                rows_written += 1

    logger.info("Wrote %d detection rows -> %s", rows_written, OUTPUT_CSV)
    return rows_written


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run YOLOv8 object detection over scraped images.")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Ultralytics model (default: yolov8n.pt).")
    p.add_argument("--conf", type=float, default=DEFAULT_CONF, help="Confidence threshold.")
    p.add_argument("--limit", type=int, default=None, help="Max images to process.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    detect(args.model, args.conf, args.limit)


if __name__ == "__main__":
    main()
