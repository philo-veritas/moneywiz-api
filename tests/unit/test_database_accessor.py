import pytest

from moneywiz_api.database_accessor import DatabaseAccessor


def _build_accessor() -> DatabaseAccessor:
    accessor = DatabaseAccessor.__new__(DatabaseAccessor)
    accessor._ent_to_typename = {37: "DepositTransaction"}
    accessor._typename_to_ent = {"DepositTransaction": 37}
    return accessor


def test_typename_for_returns_typename():
    accessor = _build_accessor()
    assert accessor.typename_for(37) == "DepositTransaction"


def test_typename_for_raises_keyerror_for_unknown_ent_id():
    accessor = _build_accessor()
    with pytest.raises(KeyError, match="Unknown entity id: 999"):
        accessor.typename_for(999)


def test_ent_for_returns_ent_id():
    accessor = _build_accessor()
    assert accessor.ent_for("DepositTransaction") == 37


def test_ent_for_raises_keyerror_for_unknown_type():
    accessor = _build_accessor()
    with pytest.raises(KeyError, match="Unknown entity type: MissingType"):
        accessor.ent_for("MissingType")
