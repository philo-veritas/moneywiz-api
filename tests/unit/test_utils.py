from datetime import datetime

from moneywiz_api.utils import get_datetime, get_date


def test_get_datetime_roundtrip():
    dt = datetime(2023, 6, 15, 12, 30, 0)
    raw = get_date(dt)
    restored = get_datetime(raw)
    assert restored == dt


def test_get_datetime_epoch():
    result = get_datetime(0.0)
    assert result == datetime(2001, 1, 1, 0, 0, 0)


def test_get_date_returns_float():
    dt = datetime(2024, 1, 1, 0, 0, 0)
    result = get_date(dt)
    assert isinstance(result, float)
    assert result > 0
