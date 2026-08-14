"""Lone hesitation is not a topic pivot."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processors.pivot_detector import PivotDetectorProcessor  # noqa: E402


def test_lone_wait_is_not_a_pivot():
    detector = PivotDetectorProcessor()
    assert detector._pattern_pivot("wait") is False
    assert detector._pattern_pivot("hold on") is False
    assert detector._pattern_pivot("Wait.") is False


def test_real_redirect_is_still_a_pivot():
    detector = PivotDetectorProcessor()
    assert detector._pattern_pivot("actually let's do something else") is True
    assert detector._pattern_pivot("wait, by the way different question") is True
