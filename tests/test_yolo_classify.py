"""Unit tests for the YOLO image-category classification scheme.

Tests the pure _classify helper, so they run without ultralytics/torch.
"""
from src.yolo_detect import _classify


def test_promotional_person_and_product():
    assert _classify({"person", "bottle"}) == "promotional"


def test_product_display_product_no_person():
    assert _classify({"bottle"}) == "product_display"
    assert _classify({"cup", "bowl"}) == "product_display"


def test_lifestyle_person_no_product():
    assert _classify({"person"}) == "lifestyle"
    assert _classify({"person", "car"}) == "lifestyle"


def test_other_neither():
    assert _classify(set()) == "other"
    assert _classify({"car", "tv"}) == "other"
