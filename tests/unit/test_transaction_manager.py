from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from moneywiz_api.managers.transaction_manager import TransactionManager
from moneywiz_api.model.transaction import TransferBudgetTransaction


def _make_txn(id, dt, amount=Decimal("100"), cls=None):
    if cls is TransferBudgetTransaction:
        txn = MagicMock(spec=TransferBudgetTransaction)
    else:
        txn = MagicMock()
        txn.account = 1
    txn.id = id
    txn.gid = f"gid-{id}"
    txn.datetime = dt
    txn.amount = amount
    return txn


def _build_manager(*txns):
    tm = TransactionManager.__new__(TransactionManager)
    tm._records = {t.id: t for t in txns}
    tm._gid_to_id = {t.gid: t.id for t in txns}
    tm.category_assignment = {}
    tm.refund_maps = {}
    tm.tags_map = {}
    tm._category_to_transactions = {}
    return tm


def test_filter_excludes_transfer_budget():
    t1 = _make_txn(1, datetime(2024, 1, 1))
    t2 = _make_txn(2, datetime(2024, 1, 2), cls=TransferBudgetTransaction)
    t3 = _make_txn(3, datetime(2024, 1, 3))
    tm = _build_manager(t1, t2, t3)
    result = tm._filter([t1, t2, t3])
    assert len(result) == 2
    assert all(not isinstance(t, TransferBudgetTransaction) for t in result)


def test_filter_since():
    t1 = _make_txn(1, datetime(2024, 1, 1))
    t2 = _make_txn(2, datetime(2024, 6, 1))
    tm = _build_manager(t1, t2)
    result = tm._filter([t1, t2], since=datetime(2024, 3, 1))
    assert len(result) == 1
    assert result[0].id == 2


def test_filter_until():
    t1 = _make_txn(1, datetime(2024, 1, 1))
    t2 = _make_txn(2, datetime(2024, 6, 1))
    tm = _build_manager(t1, t2)
    result = tm._filter([t1, t2], until=datetime(2024, 3, 1))
    assert len(result) == 1
    assert result[0].id == 1


def test_filter_since_and_until():
    t1 = _make_txn(1, datetime(2024, 1, 1))
    t2 = _make_txn(2, datetime(2024, 6, 1))
    t3 = _make_txn(3, datetime(2024, 12, 1))
    tm = _build_manager(t1, t2, t3)
    result = tm._filter(
        [t1, t2, t3],
        since=datetime(2024, 3, 1),
        until=datetime(2024, 9, 1),
    )
    assert len(result) == 1
    assert result[0].id == 2


def test_filter_sorted_by_datetime():
    t1 = _make_txn(1, datetime(2024, 6, 1))
    t2 = _make_txn(2, datetime(2024, 1, 1))
    t3 = _make_txn(3, datetime(2024, 3, 1))
    tm = _build_manager(t1, t2, t3)
    result = tm._filter([t1, t2, t3])
    assert [t.id for t in result] == [2, 3, 1]
