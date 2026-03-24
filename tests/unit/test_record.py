from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from moneywiz_api.model.record import Record


def _make_record():
    row = {
        "Z_PK": 1,
        "Z_ENT": 10,
        "ZGID": "gid-1",
        "ZOBJECTCREATIONDATE": 700000000.0,  # Core Data epoch offset
    }
    with patch.object(Record, "__init_subclass__", lambda **kw: None):
        record = Record.__new__(Record)
        record._raw = row
        record._ent = row["Z_ENT"]
        record._created_at = datetime(2023, 3, 8, 1, 46, 40)
        record.gid = row["ZGID"]
        record.id = row["Z_PK"]
    return record


def test_as_dict_excludes_underscore_fields():
    record = _make_record()
    d = record.as_dict()
    assert "id" in d
    assert "gid" in d
    for key in d:
        assert not key.startswith("_"), f"Unexpected private key: {key}"


def test_to_dict_converts_decimal():
    d = Record._convert_values({"amount": Decimal("123.45")})
    assert d["amount"] == 123.45
    assert isinstance(d["amount"], float)


def test_to_dict_converts_datetime():
    dt = datetime(2024, 6, 15, 10, 30, 0)
    d = Record._convert_values({"date": dt})
    assert d["date"] == "2024-06-15T10:30:00"
    assert isinstance(d["date"], str)


def test_to_dict_preserves_primitives():
    d = Record._convert_values({"name": "test", "count": 42, "flag": True})
    assert d == {"name": "test", "count": 42, "flag": True}


def test_to_dict_handles_nested_dict():
    d = Record._convert_values({"nested": {"amount": Decimal("10")}})
    assert d["nested"]["amount"] == 10.0


def test_to_dict_handles_list():
    d = Record._convert_values({"items": [Decimal("1.5"), Decimal("2.5")]})
    assert d["items"] == [1.5, 2.5]


def test_convert_value_none():
    d = Record._convert_values({"x": None})
    assert d["x"] is None
